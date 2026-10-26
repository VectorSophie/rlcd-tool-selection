"""Experiment runner. Enforces the cross-arm invariants before any model is called."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from datetime import timezone

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import FatalRunError, Task
from rlcdselect.eval.budget import BudgetGuard
from rlcdselect.eval.logging import JsonlWriter, build_record
from rlcdselect.pipelines.base import Pipeline


class InvariantError(ValueError):
    """The configured arms would not form a matched comparison."""


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    order_seeds: tuple[int | None, ...] = (None,)
    id_seed: int | None = None
    samples_per_condition: int = 1  # repeated sampling for empirical selection frequencies
    profile: str | None = None  # e.g. "deterministic_v1"; recorded on every run
    condition: str | None = None  # e.g. "architecture_matched_v1"; recorded on every run
    # Where tools came from and how they were executed, e.g. {"registry": "mcp", "executor": "mcp",
    # "servers": [...]}; recorded on every run.
    tool_source: dict[str, Any] | None = None
    # Per-task presentation orderings, overriding `order_seeds` for the listed tasks. Needed when
    # tasks share a candidate count: one shared seed would apply the same permutation to all of
    # them and move a source-position bias instead of removing it.
    task_order_seeds: dict[str, tuple[int | None, ...]] | None = None
    # Fields copied into every record, e.g. {"manifest_hash": ..., "dataset": ..., "run_group": ...}.
    record_fields: dict[str, Any] | None = None

    def seeds_for(self, task_id: str) -> tuple[int | None, ...]:
        if self.task_order_seeds is not None and task_id in self.task_order_seeds:
            return tuple(self.task_order_seeds[task_id])
        return self.order_seeds


def check_invariants(pipelines: Sequence[Pipeline]) -> None:
    """All arms must share one LLM config and one serialization config."""
    ids = [p.pipeline_id for p in pipelines]
    if len(set(ids)) != len(ids):
        raise InvariantError(f"Duplicate pipeline ids: {ids}")
    configs = [(p.pipeline_id, c) for p in pipelines for c in p.llm_configs()]
    if configs and any(c != configs[0][1] for _, c in configs):
        detail = {pid: thaw(c) for pid, c in configs}
        raise InvariantError(f"Arms use different LLM configs; one shared LLM is required: {detail}")
    serializations = {p.pipeline_id: p.serialization for p in pipelines}
    if len(set(serializations.values())) > 1:
        raise InvariantError(f"Arms use different serialization configs: {thaw(serializations)}")
    native = [p.pipeline_id for p in pipelines if p.describe().get("native_single_call")]
    if native and any(p.serialization.allow_duplicate_names for p in pipelines):
        raise InvariantError(f"Duplicate-name stress conditions are decomposed-only; remove native arms {native}")


async def run_experiment(
    tasks: Sequence[Task],
    pipelines: Sequence[Pipeline],
    config: ExperimentConfig,
    writer: JsonlWriter | None = None,
    clock: Callable[[], datetime] | None = None,
    budget: BudgetGuard | None = None,
) -> list[dict[str, Any]]:
    """Run every task × order seed × sample × pipeline. With a `budget`, actual spend is charged after
    each run and the experiment aborts (with a `run_aborted` record) once the cap is reached."""
    check_invariants(pipelines)
    shuffle_needed = [t.task_id for t in tasks if "requires_order_shuffle" in t.tags]
    if any(all(seed is None for seed in config.seeds_for(t)) for t in shuffle_needed):
        raise InvariantError(
            f"{len(shuffle_needed)} task(s) have a known source-order bias (e.g. MetaTool: gold always first) "
            "and need at least one seeded order permutation; source order cannot be the only condition")
    records = []
    for task in tasks:
        for order_seed in config.seeds_for(task.task_id):
            for sample_index in range(config.samples_per_condition):
                for pipeline in pipelines:
                    try:
                        outcome = await pipeline.run(task, order_seed=order_seed, id_seed=config.id_seed)
                    except FatalRunError as exc:
                        _abort(exc, config, task, pipeline, order_seed, sample_index, writer, clock, budget)
                        raise
                    record = build_record(
                        experiment_id=config.experiment_id, task=task, pipeline=pipeline, outcome=outcome,
                        order_seed=order_seed, id_seed=config.id_seed, sample_index=sample_index,
                        timestamp=clock() if clock else None,
                        profile=config.profile, condition=config.condition,
                    )
                    children = [
                        build_record(
                            experiment_id=config.experiment_id, task=task, pipeline=pipeline, outcome=child,
                            order_seed=order_seed, id_seed=config.id_seed, sample_index=sample_index,
                            timestamp=clock() if clock else None, profile=config.profile,
                            condition=config.condition, selector_sample_index=i,
                        )
                        for i, child in outcome.sample_outcomes
                    ]
                    for rec in (record, *children):
                        rec["tool_source"] = thaw(config.tool_source)
                        rec.update(thaw(config.record_fields or {}))
                        if budget is not None:
                            rec["cost_charged_usd"] = budget.charge(rec)
                            rec["budget_spent_usd"] = budget.spent_usd
                        if writer is not None:
                            writer.write(rec)
                        records.append(rec)
                    if budget is not None:
                        try:
                            budget.check()
                        except FatalRunError as exc:
                            _abort(exc, config, task, pipeline, order_seed, sample_index, writer, clock, budget)
                            raise
    return records


def _abort(exc: FatalRunError, config: ExperimentConfig, task: Task, pipeline: Pipeline, order_seed, sample_index,
           writer: JsonlWriter | None, clock, budget: BudgetGuard | None) -> None:
    # A call that tripped a fatal check was still made and billed; charge its reported cost.
    if budget is not None and isinstance(exc.raw, dict) and isinstance(exc.raw.get("cost"), (int, float)):
        budget.spent_usd += exc.raw["cost"]
        budget.reported_usd += exc.raw["cost"]
    abort = {
        "record_type": "run_aborted",
        "experiment_id": config.experiment_id,
        "profile": config.profile,
        "condition": config.condition,
        "task_id": task.task_id,
        "pipeline": pipeline.pipeline_id,
        "order_seed": order_seed,
        "sample_index": sample_index,
        "error_kind": exc.kind,
        "message": str(exc),
        "detail": thaw(exc.raw),
        "budget": budget.summary() if budget is not None else None,
        "timestamp": (clock() if clock else datetime.now(timezone.utc)).isoformat(),
    }
    if writer is not None:
        writer.write(abort)
