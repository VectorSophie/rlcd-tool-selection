"""Pipelines B and C: a dedicated selector picks one tool; the shared argument generator fills it."""

import dataclasses
from collections.abc import Sequence
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.prompts import PROMPT_VERSION
from rlcdselect.core.retry import call_with_retry, error_kind, total_latency
from rlcdselect.core.serialization import (
    CandidateSet,
    SelectorRequest,
    SerializationConfig,
    SerializationError,
    build_selector_request,
    present_task,
)
from rlcdselect.core.types import (
    ErrorInfo,
    LLMConfig,
    RetryPolicy,
    SelectionResult,
    SelectionStatus,
    SelectorSamplingPolicy,
    Task,
)
from rlcdselect.execution.base import ToolExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.pipelines.base import (
    SKIPPED_ARGUMENTS,
    PipelineOutcome,
    error_selection,
    execute_if_ready,
    presentation_failure,
    validate_probabilities,
)
from rlcdselect.selectors.base import Selector


class DecomposedPipeline:
    """Selection by `selector`, then the shared argument generator, then execution.

    With `sampling.repetitions` > 1 the identical selector request is sent N times and every
    sample is kept (`PipelineOutcome.selector_samples`). Only sample
    `sampling.execution_sample_index` (default 0) continues to argument generation and execution,
    unless `sampling.execute_each_sample` is set. It is never chosen by majority vote.
    """

    def __init__(self, selector: Selector, arguments: ArgumentGenerator, executor: ToolExecutor,
                 serialization: SerializationConfig, retry: RetryPolicy = RetryPolicy(),
                 sampling: SelectorSamplingPolicy = SelectorSamplingPolicy()) -> None:
        self.selector = selector
        self.argument_generator = arguments
        self.executor = executor
        self.serialization = serialization
        self.retry = retry
        self.sampling = sampling

    @property
    def pipeline_id(self) -> str:
        return self.selector.selector_id

    def describe(self) -> dict[str, Any]:
        arg_cfg = self.argument_generator.client.config
        sel_cfg = self.selector.llm_config
        return {
            "selector_id": self.selector.selector_id,
            "selector_model": self.selector.model,
            "selector_llm_config": thaw(sel_cfg) if sel_cfg else None,
            "argument_model": f"{arg_cfg.provider}/{arg_cfg.model}",
            "llm_config": thaw(arg_cfg),
            "native_single_call": False,
            "prompt_version": PROMPT_VERSION,
            "selector_prompt_version": getattr(self.selector, "prompt_version", None),
            "selector_sampling": thaw(self.sampling),
        }

    def llm_configs(self) -> Sequence[LLMConfig]:
        configs = [self.argument_generator.client.config]
        if self.selector.llm_config is not None:
            configs.append(self.selector.llm_config)
        return configs

    async def run(self, task: Task, *, order_seed: int | None, id_seed: int | None) -> PipelineOutcome:
        try:
            cset = present_task(task, self.serialization, order_seed=order_seed, id_seed=id_seed)
            request = build_selector_request(task.state, cset, self.serialization)
        except SerializationError as exc:
            return presentation_failure(self.pipeline_id, exc)

        samples: list[SelectionResult] = []
        payloads: list[Any] = []
        for _ in range(self.sampling.repetitions):  # identical request every time
            selection, payload = await self._select_once(request, cset)
            samples.append(selection)
            payloads.append(payload)

        k = self.sampling.execution_sample_index
        outcome = await self._continue(task, cset, request, samples[k], payloads[k])
        if self.sampling.repetitions == 1:
            return outcome
        children: list[tuple[int, PipelineOutcome]] = []
        if self.sampling.execute_each_sample:
            for i, (sel, payload) in enumerate(zip(samples, payloads)):
                if i != k:
                    children.append((i, await self._continue(task, cset, request, sel, payload)))
        return dataclasses.replace(outcome, selector_samples=tuple(samples), sample_outcomes=tuple(children),
                                   execution_sample_index=k)

    async def _select_once(self, request: SelectorRequest, cset: CandidateSet) -> tuple[SelectionResult, Any]:
        """One selection call, validated. Returns the result and the provider payload sent."""
        kind = self.selector.probability_kind
        output, exc, attempts = await call_with_retry(lambda: self.selector.select(request), self.retry)
        latency = total_latency(attempts)
        if output is None:
            selection = error_selection(ErrorInfo("selection", error_kind(exc), str(exc)),
                                        latency_ms=latency, attempts=attempts, kind=kind,
                                        raw=getattr(exc, "raw", None),
                                        provider_meta=getattr(exc, "provider_meta", None))
            return selection, None

        if output.choice not in request.criteria:
            status, cid, error = SelectionStatus.ERROR, None, ErrorInfo(
                "selection", "invalid_choice", f"Selector returned {output.choice!r}, not an offered option")
        elif output.choice == request.abstain_id:
            status, cid, error = SelectionStatus.ABSTAINED, None, None
        else:
            status, cid, error = SelectionStatus.SELECTED, output.choice, None

        selection = SelectionResult(
            status=status,
            selected_candidate_id=cid,
            selected_tool_key=cset.by_id(cid).tool.key if cid else None,
            probabilities=thaw(output.probabilities) if output.probabilities is not None else None,
            probability_kind=kind,
            probability_issues=validate_probabilities(output.probabilities, request.option_ids),
            confidence=output.confidence,
            raw_response=output.raw,
            latency_ms=latency,
            usage=output.usage,
            model_reported=output.model_reported,
            error=error,
            attempts=attempts,
            provider_meta=output.provider_meta,
        )
        return selection, output.request_payload

    async def _continue(self, task: Task, cset: CandidateSet, request: SelectorRequest,
                        selection: SelectionResult, payload: Any) -> PipelineOutcome:
        """Argument generation and execution for one selection (skipped unless a tool was selected)."""
        inputs: dict[str, Any] = {"selection": {"request": thaw(request), "provider_payload": payload}}
        if selection.status is not SelectionStatus.SELECTED:
            return PipelineOutcome(self.pipeline_id, cset, selection, SKIPPED_ARGUMENTS, None, inputs)
        cid = selection.selected_candidate_id
        arguments, arg_request, arg_payload = await self.argument_generator.generate(task.state, cset.by_id(cid))
        inputs["arguments"] = {"request": thaw(arg_request), "provider_payload": arg_payload}
        execution = await execute_if_ready(self.executor, task, selection, arguments)
        return PipelineOutcome(self.pipeline_id, cset, selection, arguments, execution, inputs)
