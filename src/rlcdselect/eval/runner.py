"""Experiment runner. Enforces the cross-arm invariants before any model is called."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import Task
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


async def run_experiment(
    tasks: Sequence[Task],
    pipelines: Sequence[Pipeline],
    config: ExperimentConfig,
    writer: JsonlWriter | None = None,
    clock: Callable[[], datetime] | None = None,
) -> list[dict[str, Any]]:
    check_invariants(pipelines)
    records = []
    for task in tasks:
        for order_seed in config.order_seeds:
            for sample_index in range(config.samples_per_condition):
                for pipeline in pipelines:
                    outcome = await pipeline.run(task, order_seed=order_seed, id_seed=config.id_seed)
                    record = build_record(
                        experiment_id=config.experiment_id, task=task, pipeline=pipeline, outcome=outcome,
                        order_seed=order_seed, id_seed=config.id_seed, sample_index=sample_index,
                        timestamp=clock() if clock else None,
                    )
                    if writer is not None:
                        writer.write(record)
                    records.append(record)
    return records
