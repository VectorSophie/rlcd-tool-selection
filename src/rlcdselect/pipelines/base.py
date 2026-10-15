import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from rlcdselect.core.serialization import CandidateSet, SerializationConfig
from rlcdselect.core.types import (
    ArgumentResult,
    ArgumentStatus,
    ErrorInfo,
    LLMConfig,
    ProbabilityKind,
    SelectionResult,
    SelectionStatus,
    Task,
    ToolExecutionResult,
)
from rlcdselect.execution.base import ToolExecutor

PROBABILITY_SUM_TOLERANCE = 1e-3


@dataclass(frozen=True)
class PipelineOutcome:
    pipeline_id: str
    candidate_set: CandidateSet | None
    selection: SelectionResult
    arguments: ArgumentResult
    execution: ToolExecutionResult | None
    model_inputs: Mapping[str, Any]  # exactly what each model call received, keyed by stage


class Pipeline(Protocol):
    @property
    def pipeline_id(self) -> str: ...

    @property
    def serialization(self) -> SerializationConfig: ...

    def describe(self) -> dict[str, Any]:
        """Models and configs, for the run record."""
        ...

    def llm_configs(self) -> Sequence[LLMConfig]:
        """Every LLM config this pipeline uses; the runner requires them to be identical across arms."""
        ...

    async def run(self, task: Task, *, order_seed: int | None, id_seed: int | None) -> PipelineOutcome: ...


SKIPPED_ARGUMENTS = ArgumentResult(ArgumentStatus.SKIPPED, None, None, (), None, None, None, None)


def error_selection(error: ErrorInfo, *, latency_ms: float = 0.0, attempts=(), raw=None,
                    kind: ProbabilityKind = ProbabilityKind.NONE, provider_meta=None) -> SelectionResult:
    return SelectionResult(
        status=SelectionStatus.ERROR, selected_candidate_id=None, selected_tool_key=None,
        probabilities=None, probability_kind=kind, probability_issues=(), confidence=None,
        raw_response=raw, latency_ms=latency_ms, usage=None, model_reported=None, error=error,
        attempts=tuple(attempts), provider_meta=provider_meta,
    )


def presentation_failure(pipeline_id: str, exc: Exception) -> PipelineOutcome:
    err = ErrorInfo("presentation", "serialization_error", str(exc))
    return PipelineOutcome(pipeline_id, None, error_selection(err), SKIPPED_ARGUMENTS, None, {})


def validate_probabilities(probabilities: Mapping[str, Any] | None, option_ids: Sequence[str]) -> tuple[str, ...]:
    """Report problems with a probability map. The map itself is never altered or renormalized."""
    if probabilities is None:
        return ()
    issues = []
    keys, expected = set(probabilities), set(option_ids)
    if keys - expected:
        issues.append(f"unknown_keys={sorted(keys - expected)}")
    if expected - keys:
        issues.append(f"missing_keys={sorted(expected - keys)}")
    valid = []
    for k, v in probabilities.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1:
            issues.append(f"invalid_value[{k}]={v!r}")
        else:
            valid.append(float(v))
    total = sum(valid)
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        issues.append(f"sum={total:.6f}")
    return tuple(issues)


async def execute_if_ready(executor: ToolExecutor, task: Task, selection: SelectionResult,
                           arguments: ArgumentResult) -> ToolExecutionResult | None:
    if selection.status is not SelectionStatus.SELECTED or arguments.status is not ArgumentStatus.OK:
        return None
    return await executor.call_tool(task.tool(selection.selected_tool_key), arguments.arguments)
