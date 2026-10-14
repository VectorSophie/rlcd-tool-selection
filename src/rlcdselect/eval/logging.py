"""Run records: one JSON object per run, sufficient to reproduce the run's inputs.

Records are redacted before writing: values under credential-like keys are replaced, and the values
of known API-key environment variables are scrubbed from every string.
"""

import json
import os
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rlcdselect.core.jsonutil import sha256_hex, thaw
from rlcdselect.core.serialization import ABSTAIN_ID
from rlcdselect.core.types import ABSTAIN, Task, Usage
from rlcdselect.eval.scoring import score
from rlcdselect.pipelines.base import Pipeline, PipelineOutcome

RECORD_SCHEMA_VERSION = 1

SECRET_KEYS = frozenset(
    {"api_key", "apikey", "x-api-key", "api-key", "authorization", "proxy-authorization",
     "password", "secret", "client_secret", "access_token", "refresh_token", "cookie", "set-cookie"}
)
SECRET_ENV_VARS = (
    "TYPESAFE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "INCEPTION_API_KEY",
)
REDACTED = "[REDACTED]"


def secret_values_from_env(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = os.environ if env is None else env
    return tuple(v for name in SECRET_ENV_VARS if len(v := env.get(name, "")) >= 8)


def redact(value: Any, secrets: Iterable[str] = ()) -> Any:
    secrets = tuple(secrets)
    if isinstance(value, Mapping):
        return {k: REDACTED if str(k).lower() in SECRET_KEYS else redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for s in secrets:
            value = value.replace(s, REDACTED)
        return value
    return value


def run_id(experiment_id: str, task_id: str, pipeline_id: str, order_seed: int | None,
           id_seed: int | None, sample_index: int) -> str:
    return sha256_hex([experiment_id, task_id, pipeline_id, order_seed, id_seed, sample_index])[:20]


def _usage(u: Usage | None) -> dict[str, Any] | None:
    return thaw(u) if u is not None else None


def _tool_json(tool) -> dict[str, Any]:
    return {"key": tool.key, **thaw(tool)}


def build_record(*, experiment_id: str, task: Task, pipeline: Pipeline, outcome: PipelineOutcome,
                 order_seed: int | None, id_seed: int | None, sample_index: int,
                 timestamp: datetime | None = None) -> dict[str, Any]:
    desc = pipeline.describe()
    sel, args, exe, cset = outcome.selection, outcome.arguments, outcome.execution, outcome.candidate_set
    scored = score(task, outcome)

    probabilities_by_tool = None
    if sel.probabilities is not None and cset is not None:
        # Keyed by stable tool key so clean and perturbed runs can be aligned even if ids differ.
        id_map = cset.id_map
        probabilities_by_tool = {}
        for cid, p in sel.probabilities.items():
            if cid in id_map:
                probabilities_by_tool[id_map[cid]] = p
            elif cid == ABSTAIN_ID:
                probabilities_by_tool[ABSTAIN] = p
            else:
                probabilities_by_tool[f"unknown:{cid}"] = p

    errors = [e for e in (sel.error, args.error, exe.error if exe else None) if e is not None]
    exec_latency = exe.latency_ms if exe else None
    parts = [sel.latency_ms, args.latency_ms, exec_latency]
    tools = [_tool_json(t) for t in task.tools]

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "run_id": run_id(experiment_id, task.task_id, outcome.pipeline_id, order_seed, id_seed, sample_index),
        "experiment_id": experiment_id,
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "task_id": task.task_id,
        "task_tags": list(task.tags),
        "seed": order_seed,
        "order_seed": order_seed,
        "id_seed": id_seed,
        "sample_index": sample_index,
        "pipeline": outcome.pipeline_id,
        **desc,
        "state": thaw(task.state),
        "state_hash": sha256_hex(task.state),
        "serialization": thaw(pipeline.serialization),
        "candidate_representation": ("native_function_schema" if desc.get("native_single_call")
                                     else pipeline.serialization.representation.value),
        "tools_before": tools,
        "tools_after": tools,  # identical until perturbations exist (Phase 5)
        "perturbation": None,
        "tool_order": list(cset.tool_order) if cset else None,
        "candidate_ids": cset.id_map if cset else None,
        "expected": {
            "tool_keys": sorted(task.expected.tool_keys),
            "abstain_reason": task.expected.abstain_reason,
            "argument_constraints": thaw(task.expected.argument_constraints),
        },
        "expected_tool": sorted(task.expected.tool_keys) or ABSTAIN,
        "roles": {k: v.value for k, v in task.roles.items()},
        "model_inputs": thaw(outcome.model_inputs),
        "selection_status": sel.status.value,
        "selected_candidate_id": sel.selected_candidate_id,
        "selected_tool": sel.selected_tool_key,
        "selection_probabilities": thaw(sel.probabilities),
        "selection_probabilities_by_tool": probabilities_by_tool,
        "probability_kind": sel.probability_kind.value,
        "probability_issues": list(sel.probability_issues),
        "selection_confidence": sel.confidence,
        "selector_model_reported": sel.model_reported,
        "argument_status": args.status.value,
        "arguments": thaw(args.arguments),
        "argument_schema_errors": list(args.schema_errors),
        "execution_output": thaw(exe.output) if exe else None,
        **scored,
        "selection_latency_ms": sel.latency_ms,
        "argument_latency_ms": args.latency_ms,
        "execution_latency_ms": exec_latency,
        "total_latency_ms": sum(p for p in parts if p is not None),
        "selector_usage": _usage(sel.usage),
        "argument_usage": _usage(args.usage),
        "retry_count": sel.retry_count + args.retry_count,
        "selection_attempts": thaw(sel.attempts),
        "argument_attempts": thaw(args.attempts),
        "errors": thaw(errors),
        "error": thaw(errors[0]) if errors else None,
        "raw": {"selection": thaw(sel.raw_response), "arguments": thaw(args.raw_response)},
    }


class JsonlWriter:
    """Append-only JSONL writer that redacts every record before writing it."""

    def __init__(self, path: str | Path, secrets: Iterable[str] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._secrets = tuple(secrets) if secrets is not None else secret_values_from_env()

    def write(self, record: Mapping[str, Any]) -> None:
        # Keys are NOT sorted: mapping order is data (e.g. criteria are in presentation order).
        line = json.dumps(redact(thaw(record), self._secrets), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
