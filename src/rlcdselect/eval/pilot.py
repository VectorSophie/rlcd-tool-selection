"""External benchmark pilot: plan, estimate, freeze, verify, execute.

The flow keeps estimation and spending apart:

1. `plan_group` samples each dataset (`datasets/external/registry.py`), builds the exact
   requests the arms will send, and estimates their cost per dataset, arm and stage. Nothing is
   sent to a model.
2. `allocate_caps` applies the approval rule: the total estimate must be within the approved
   limit (default $10), and each group's cap is its estimate × 1.5, scaled down if needed so the
   caps together never exceed the limit. Over the limit, planning stops with a cost breakdown;
   the sample is never reduced silently.
3. `freeze` writes the manifest (git commit, dataset sources and SHA-256s, adapter versions,
   sampled task ids, per-task order seeds, profile, conditions, models, routing, Jev repetitions,
   estimate, cap, timestamp) and its hash. Every record of the run carries `manifest_hash`.
4. `verify_manifest` re-derives everything from the manifest before execution: the hash, the
   commit (the working tree must be clean and at that commit), the sampled ids and order seeds,
   and the estimate. Any difference stops the run before a provider call.
5. `execute_group` runs each dataset of the group under its own condition, with one shared budget
   guard, into one records file that must not already exist (a fixed bug means a new manifest and
   a new run, never a mixed run set).
"""

import hashlib
import json
import math
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import SelectorSamplingPolicy
from rlcdselect.datasets.external.registry import DATASETS, sample_dataset
from rlcdselect.eval.budget import BudgetGuard, Prices, estimate_task_cost_stages
from rlcdselect.eval.logging import JsonlWriter
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.profiles import CONDITIONS, JEV_EXPECTED_RETURNED_MODELS, JEV_MODEL, ExperimentProfile

ARMS = ("native_llm", "matched_llm", "jev")
MANIFEST_VERSION = "external_pilot_manifest_v1"
DEFAULT_APPROVED_LIMIT_USD = 10.0
CAP_FACTOR = 1.5


class PlanError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def git_state(repo: Path | str = ".") -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    # Run outputs (manifests, records, summaries) live under results/ and do not make the code dirty;
    # any other change, including an untracked source file, does.
    changes = [line for line in git("status", "--porcelain", "--untracked-files=all").splitlines()
               if not line[3:].startswith("results/")]
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(changes), "uncommitted": changes[:20]}


def jev_policy(repetitions: int) -> SelectorSamplingPolicy:
    return SelectorSamplingPolicy(repetitions=repetitions, execution_sample_index=0)


def estimate_sample(sample, prices: Prices, jev_repetitions: int, arms: Sequence[str] = ARMS) -> dict[str, Any]:
    serialization = CONDITIONS[sample.spec.condition]
    sampling = {"jev": jev_policy(jev_repetitions)}
    by_arm = {a: {"selection": 0.0, "arguments": 0.0} for a in arms}
    for task in sample.tasks:
        for arm, stages in estimate_task_cost_stages(task, arms, serialization, prices, "discrete", sampling).items():
            for stage, v in stages.items():
                by_arm[arm][stage] += v
    total = sum(v for s in by_arm.values() for v in s.values())
    return {"total_usd": total, "by_arm": by_arm}


def plan_group(group: str, datasets: Sequence[tuple[str, int | None]], *, seed: int, stratify: bool,
               profile: ExperimentProfile, jev_repetitions: int, prices: Prices,
               arms: Sequence[str] = ARMS) -> dict[str, Any]:
    entries, total = [], 0.0
    for name, size in datasets:
        sample = sample_dataset(name, size, seed, stratify)
        est = estimate_sample(sample, prices, jev_repetitions, arms)
        total += est["total_usd"]
        entries.append({
            "dataset": name, "role": sample.spec.role, "condition": sample.spec.condition,
            "serialization": thaw(CONDITIONS[sample.spec.condition]), "notes": sample.spec.notes,
            **sample.info,
            "task_ids": [t.task_id for t in sample.tasks],
            "order_seeds": sample.order_seeds,
            "cluster_ids": {t.task_id: (t.provenance or {}).get("source_group_id") for t in sample.tasks
                            if (t.provenance or {}).get("source_group_id") is not None} or None,
            "estimate": est,
        })
    return {
        "manifest_version": MANIFEST_VERSION,
        "group": group,
        "seed": seed,
        "stratify": stratify,
        "orderings_per_task": 1,
        "arms": list(arms),
        "profile": profile.name,
        "llm_config": thaw(profile.llm),
        "jev": {"model": JEV_MODEL, "expected_returned_models": list(JEV_EXPECTED_RETURNED_MODELS),
                "selector_repetitions": jev_repetitions, "execution_sample_index": 0,
                "draws": "back-to-back (no temporal spacing)"},
        "executor": "mock",
        "prices": asdict(prices),
        "datasets": entries,
        "estimate_usd": total,
    }


def allocate_caps(plans: Sequence[dict[str, Any]], limit_usd: float = DEFAULT_APPROVED_LIMIT_USD,
                  factor: float = CAP_FACTOR) -> None:
    """Set each plan's `budget_cap_usd`, or raise `PlanError` with a breakdown when over the limit."""
    total = sum(p["estimate_usd"] for p in plans)
    if total > limit_usd:
        lines = [f"Estimated ${total:.2f} exceeds the approved ${limit_usd:.2f}. Nothing will run."]
        for p in sorted(plans, key=lambda p: -p["estimate_usd"]):
            lines.append(f"  group {p['group']}: ${p['estimate_usd']:.2f}")
            for d in p["datasets"]:
                arms = ", ".join(f"{a} ${sum(s.values()):.2f}" for a, s in d["estimate"]["by_arm"].items())
                lines.append(f"    {d['dataset']} ({d['sample_size']}): ${d['estimate']['total_usd']:.2f} [{arms}]")
        raise PlanError("\n".join(lines))
    scale = min(factor, limit_usd / total) if total else factor
    for p in plans:
        # Rounded down to a micro-dollar, never below the estimate itself.
        p["budget_cap_usd"] = max(p["estimate_usd"], math.floor(p["estimate_usd"] * scale * 1e6) / 1e6)
        p["budget_rule"] = {"approved_limit_usd": limit_usd, "factor": factor, "applied_scale": scale,
                            "all_groups_estimate_usd": total}


def freeze(plan: dict[str, Any], out_dir: Path, *, repo: Path | str = ".", allow_dirty: bool = False) -> Path:
    state = git_state(repo)
    if state["dirty"] and not allow_dirty:
        raise PlanError("Working tree has uncommitted changes; commit before freezing a manifest")
    if "budget_cap_usd" not in plan:
        raise PlanError("No budget cap allocated (allocate_caps first)")
    plan = {**plan, "git_commit": state["commit"], "git_dirty": state["dirty"],
            "created_at": datetime.now(timezone.utc).isoformat()}
    plan["manifest_hash"] = manifest_hash(plan)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "manifest.json"
    if path.exists():
        raise PlanError(f"{path} exists; a frozen manifest is never overwritten")
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def verify_manifest(manifest: Mapping[str, Any], prices: Prices | None = None, *, repo: Path | str = ".",
                    check_git: bool = True) -> list:
    """Re-derive the manifest's samples; return them, or raise `PlanError` on any difference."""
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise PlanError(f"Unknown manifest version {manifest.get('manifest_version')!r}")
    if manifest_hash(manifest) != manifest.get("manifest_hash"):
        raise PlanError("Manifest hash mismatch: the manifest was edited after freezing")
    if check_git:
        state = git_state(repo)
        if state["commit"] != manifest["git_commit"] or state["dirty"]:
            raise PlanError(f"Code differs from the manifest's commit {manifest['git_commit'][:12]} "
                            f"(HEAD {state['commit'][:12]}, dirty={state['dirty']})")
    cap = manifest["budget_cap_usd"]
    rule = manifest["budget_rule"]
    if not (manifest["estimate_usd"] <= cap <= rule["approved_limit_usd"]):
        raise PlanError(f"Cap ${cap} is not within [estimate ${manifest['estimate_usd']:.4f}, "
                        f"limit ${rule['approved_limit_usd']}]")
    samples = []
    for entry in manifest["datasets"]:
        sample = sample_dataset(entry["dataset"], entry["sample_size"], manifest["seed"], manifest["stratify"])
        if [t.task_id for t in sample.tasks] != entry["task_ids"] or sample.order_seeds != entry["order_seeds"]:
            raise PlanError(f"{entry['dataset']}: re-derived sample differs from the manifest")
        if entry["condition"] != sample.spec.condition:
            raise PlanError(f"{entry['dataset']}: condition changed")
        if prices is not None:
            est = estimate_sample(sample, prices, manifest["jev"]["selector_repetitions"], manifest["arms"])
            if not math.isclose(est["total_usd"], entry["estimate"]["total_usd"], rel_tol=1e-9):
                raise PlanError(f"{entry['dataset']}: estimate differs from the manifest")
        samples.append(sample)
    return samples


PipelineFactory = Callable[[Any, Any], list]  # (serialization, jev sampling policy) -> pipelines


async def execute_group(manifest: Mapping[str, Any], samples: Sequence, make_pipelines: PipelineFactory,
                        records_path: Path, *, prices: Prices) -> tuple[list[dict[str, Any]], BudgetGuard]:
    """Run a verified manifest. `make_pipelines` builds the arms for one serialization condition."""
    if records_path.exists():
        raise PlanError(f"{records_path} exists; a run set is never appended to or mixed")
    budget = BudgetGuard(cap_usd=manifest["budget_cap_usd"], prices=prices)
    budget.check_estimate({"total_usd": manifest["estimate_usd"]})
    writer = JsonlWriter(records_path)
    records: list[dict[str, Any]] = []
    for entry, sample in zip(manifest["datasets"], samples):
        serialization = CONDITIONS[entry["condition"]]
        pipelines = make_pipelines(serialization, jev_policy(manifest["jev"]["selector_repetitions"]))
        if [p.pipeline_id for p in pipelines] != list(manifest["arms"]):
            raise PlanError(f"Pipelines {[p.pipeline_id for p in pipelines]} differ from the manifest arms")
        config = ExperimentConfig(
            experiment_id=f"external_pilot__{manifest['group']}__{entry['dataset']}",
            order_seeds=(None,),
            task_order_seeds={tid: (seed,) for tid, seed in entry["order_seeds"].items()},
            profile=manifest["profile"], condition=entry["condition"],
            tool_source={"registry": "static", "executor": manifest["executor"]},
            record_fields={"manifest_hash": manifest["manifest_hash"], "run_group": manifest["group"],
                           "dataset": entry["dataset"], "dataset_role": entry["role"]},
        )
        records += await run_experiment(sample.tasks, pipelines, config, writer, budget=budget)
    return records, budget


def estimate_report(plans: Sequence[Mapping[str, Any]]) -> str:
    """Markdown cost estimate by group, dataset, arm and stage."""
    lines = ["# External pilot cost estimate", "",
             "Conservative estimate (chars/3 tokens, fixed output allowances, x1.25 margin, live OpenRouter prices). "
             "Argument generation is assumed for every decomposed task.", "",
             "| group | dataset | tasks | condition | arm | selection $ | arguments $ | total $ |",
             "|---|---|---|---|---|---|---|---|"]
    for p in plans:
        for d in p["datasets"]:
            for arm, s in d["estimate"]["by_arm"].items():
                lines.append(f"| {p['group']} | {d['dataset']} | {d['sample_size']} | {d['condition']} | {arm} | "
                             f"{s['selection']:.4f} | {s['arguments']:.4f} | {s['selection'] + s['arguments']:.4f} |")
    lines += ["", "| group | estimate $ | cap $ |", "|---|---|---|"]
    lines += [f"| {p['group']} | {p['estimate_usd']:.4f} | {p.get('budget_cap_usd', float('nan')):.4f} |" for p in plans]
    total = sum(p["estimate_usd"] for p in plans)
    lines += ["", f"**Total estimate: ${total:.4f}** (approved limit "
              f"${plans[0].get('budget_rule', {}).get('approved_limit_usd', DEFAULT_APPROVED_LIMIT_USD):.2f})."]
    return "\n".join(lines) + "\n"
