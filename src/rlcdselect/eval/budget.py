"""Spend control for live runs.

- `estimate_run_cost`: a conservative pre-run estimate built from the requests each arm would send.
  It uses the same serialization the pipelines use, approximates tokens from characters, and applies
  a safety margin. Prices come from OpenRouter's endpoint listing at startup, or the static defaults.
- `BudgetGuard`: refuses to start when the estimate exceeds the cap. During the run it accumulates
  the actual cost OpenRouter reports (`usage.cost`) per call and aborts with `FatalRunError
  ("budget_exceeded")` once spend reaches the cap. Calls without a reported cost are charged by
  their token counts, and the record of that is kept.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from rlcdselect.core.prompts import ARGUMENT_SYSTEM_PROMPT, NATIVE_SYSTEM_PROMPT
from rlcdselect.core.serialization import build_native_tools, build_selector_request, present_task, render_state
from rlcdselect.core.types import FatalRunError, SelectorSamplingPolicy, Task
from rlcdselect.core.jsonutil import thaw

CHARS_PER_TOKEN = 3.0  # conservative for English/JSON (real ratios are usually higher)
SAFETY_MARGIN = 1.25
# Fixed prompt and schema boilerplate the System One adapter adds to every matched-LLM request.
ADAPTER_OVERHEAD_CHARS = 1500
# Expected output tokens per call type (generous; Claude outputs here are short).
PAID_SELECTORS = frozenset({"native_llm", "matched_llm", "jev"})
OUTPUT_TOKENS = {"native": 200, "arguments": 200, "matched_discrete": 40, "matched_probabilities": 150}


@dataclass(frozen=True)
class Prices:
    """USD per token."""

    llm_input: float
    llm_output: float
    jev_input: float
    source: str = "static"


DEFAULT_PRICES = Prices(llm_input=1.0e-6, llm_output=5.0e-6, jev_input=0.042e-6)  # Haiku 4.5, Jev 1.13


def prices_from_catalog(llm_endpoint: Mapping[str, Any], jev_endpoint: Mapping[str, Any] | None) -> Prices:
    lp = llm_endpoint.get("pricing") or {}
    jp = (jev_endpoint or {}).get("pricing") or {}
    return Prices(
        llm_input=float(lp["prompt"]),
        llm_output=float(lp["completion"]),
        jev_input=float(jp.get("prompt", DEFAULT_PRICES.jev_input)),
        source="openrouter_endpoints",
    )


def _tokens(chars: int) -> float:
    return chars / CHARS_PER_TOKEN


def estimate_task_cost(task: Task, pipeline_ids: Sequence[str], serialization, prices: Prices,
                       matched_mode: str = "discrete",
                       sampling: Mapping[str, SelectorSamplingPolicy] | None = None) -> dict[str, float]:
    """Estimated USD for one task × one sample, per pipeline id. `sampling` (per pipeline id)
    multiplies the selection cost by its repetitions, and the argument cost too when every draw is
    executed end to end."""
    sampling = sampling or {}
    cset = present_task(task, serialization, order_seed=None, id_seed=None)
    state = render_state(task.state)
    criteria = json.dumps(thaw(build_selector_request(task.state, cset, serialization).criteria))
    largest_tool = max(len(json.dumps(thaw(t))) for t in build_native_tools(cset)) if not serialization.allow_duplicate_names else 0
    args_cost = (_tokens(len(ARGUMENT_SYSTEM_PROMPT) + len(state) + largest_tool) * prices.llm_input
                 + OUTPUT_TOKENS["arguments"] * prices.llm_output)
    out = {}
    for pid in pipeline_ids:
        policy = sampling.get(pid) or SelectorSamplingPolicy()
        reps = policy.repetitions
        arg_runs = reps if policy.execute_each_sample else 1
        if pid == "native_llm":
            tools = json.dumps([thaw(t) for t in build_native_tools(cset)])
            out[pid] = (_tokens(len(NATIVE_SYSTEM_PROMPT) + len(state) + len(tools)) * prices.llm_input
                        + OUTPUT_TOKENS["native"] * prices.llm_output)
        elif pid == "matched_llm":
            select = (_tokens(ADAPTER_OVERHEAD_CHARS + len(state) + len(criteria)) * prices.llm_input
                      + OUTPUT_TOKENS[f"matched_{matched_mode}"] * prices.llm_output)
            out[pid] = select * reps + args_cost * arg_runs
        elif pid == "jev":
            out[pid] = _tokens(len(state) + len(criteria)) * prices.jev_input * reps + args_cost * arg_runs
        else:  # local selectors (Laya, mocks): only argument generation is paid
            out[pid] = args_cost * arg_runs
    return {k: v * SAFETY_MARGIN for k, v in out.items()}


def estimate_run_cost(tasks: Sequence[Task], pipeline_ids: Sequence[str], serialization, prices: Prices,
                      n_order_seeds: int, samples: int, matched_mode: str = "discrete",
                      sampling: Mapping[str, SelectorSamplingPolicy] | None = None) -> dict[str, Any]:
    per_pipeline: dict[str, float] = {pid: 0.0 for pid in pipeline_ids}
    for task in tasks:
        for pid, cost in estimate_task_cost(task, pipeline_ids, serialization, prices, matched_mode, sampling).items():
            per_pipeline[pid] += cost * n_order_seeds * samples
    return {"total_usd": sum(per_pipeline.values()), "per_pipeline_usd": per_pipeline,
            "runs": len(tasks) * n_order_seeds * samples * len(pipeline_ids), "prices": thaw(prices),
            "selector_sampling": {k: thaw(v) for k, v in (sampling or {}).items()},
            "method": f"chars/{CHARS_PER_TOKEN} tokens, fixed output allowances, x{SAFETY_MARGIN} margin"}


def _metas(meta: Any) -> list[Mapping[str, Any]]:
    if not meta:
        return []
    if "calls" in meta:  # matched selector with several adapter calls
        return list(meta["calls"])
    return [meta]


def _call_key(meta: Mapping[str, Any]) -> Any:
    return meta.get("generation_id") or json.dumps(thaw(meta), sort_keys=True, default=str)


@dataclass
class BudgetGuard:
    cap_usd: float
    prices: Prices = DEFAULT_PRICES
    spent_usd: float = 0.0
    reported_usd: float = 0.0  # portion taken from provider-reported cost
    estimated_usd: float = 0.0  # portion charged from token counts (no reported cost)
    calls: int = 0
    by_pipeline: dict[str, float] = field(default_factory=dict)

    def check_estimate(self, estimate: Mapping[str, Any]) -> None:
        if estimate["total_usd"] > self.cap_usd:
            raise FatalRunError("budget_exceeded",
                                f"Estimated ${estimate['total_usd']:.4f} exceeds the cap ${self.cap_usd:.4f}; "
                                "nothing was run", raw=dict(estimate))

    def charge(self, record: Mapping[str, Any]) -> float:
        """Add one run record's cost. Returns the amount charged.

        A primary record pays for its selection call, every extra selector draw in
        `selector_samples`, and its argument call. A `selector_sample_run` record pays only for its
        own argument call: its selection draw is already charged in the parent record.
        """
        cost = 0.0
        seen: list[Any] = []  # native records repeat the selection call's metadata on the arguments
        child = record.get("record_type") == "selector_sample_run"
        stages = [("argument_provider_meta", "argument_usage", record.get("argument_provider_meta"),
                   record.get("argument_usage"))]
        if not child:
            stages.insert(0, ("selection_provider_meta", "selector_usage", record.get("selection_provider_meta"),
                              record.get("selector_usage")))
            for sample in (record.get("selector_samples") or [])[1:]:  # sample 0 is the selection above
                stages.insert(1, ("selection_provider_meta", "selector_usage", sample.get("provider_meta"),
                                  sample.get("usage")))
        for meta_key, usage_key, meta, usage in stages:
            metas = [m for m in _metas(meta) if _call_key(m) not in seen]
            if not metas and meta:
                continue  # every call in this stage was already charged
            seen += [_call_key(m) for m in metas]
            reported = [m.get("cost") for m in metas if m.get("cost") is not None]
            if metas and len(reported) == len(metas):
                amount = float(sum(reported))
                self.reported_usd += amount
            elif meta_key == "selection_provider_meta" and record.get("selector_id") not in PAID_SELECTORS:
                amount = 0.0  # local selectors (Laya, mocks) cost nothing
            else:
                usage = usage or {}
                is_jev = record.get("selector_id") == "jev" and meta_key == "selection_provider_meta"
                if is_jev:
                    amount = (usage.get("input_tokens") or 0) * self.prices.jev_input
                else:
                    amount = ((usage.get("input_tokens") or 0) * self.prices.llm_input
                              + (usage.get("output_tokens") or 0) * self.prices.llm_output)
                self.estimated_usd += amount
            cost += amount
            self.calls += len(metas) if metas else (1 if usage else 0)
        self.spent_usd += cost
        pid = record.get("pipeline", "?")
        self.by_pipeline[pid] = self.by_pipeline.get(pid, 0.0) + cost
        return cost

    def check(self) -> None:
        if self.spent_usd >= self.cap_usd:
            raise FatalRunError("budget_exceeded",
                                f"Spent ${self.spent_usd:.4f} reached the cap ${self.cap_usd:.4f}; run stopped",
                                raw=self.summary())

    def summary(self) -> dict[str, Any]:
        return {"cap_usd": self.cap_usd, "spent_usd": round(self.spent_usd, 6),
                "reported_usd": round(self.reported_usd, 6), "token_estimated_usd": round(self.estimated_usd, 6),
                "by_pipeline_usd": {k: round(v, 6) for k, v in self.by_pipeline.items()}}
