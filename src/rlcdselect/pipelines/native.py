"""Pipeline A: one LLM sees every candidate tool and both selects and fills arguments in one call."""

import dataclasses

from collections.abc import Sequence
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.prompts import NATIVE_SYSTEM_PROMPT, PROMPT_VERSION
from rlcdselect.core.retry import call_with_retry, error_kind, total_latency
from rlcdselect.core.serialization import SerializationConfig, SerializationError, build_native_tools, present_task, render_state
from rlcdselect.core.types import (
    ErrorInfo,
    LLMConfig,
    ProbabilityKind,
    RetryPolicy,
    SelectionResult,
    SelectionStatus,
    Task,
)
from rlcdselect.execution.base import ToolExecutor
from rlcdselect.generation.arguments import arguments_from_call
from rlcdselect.llm.base import ChatClient, ChatRequest
from rlcdselect.pipelines.base import (
    SKIPPED_ARGUMENTS,
    PipelineOutcome,
    error_selection,
    execute_if_ready,
    presentation_failure,
)


class NativePipeline:
    """The serialization config only governs naming and order here; native calling always exposes
    full descriptions and schemas, and that difference from the decomposed arms is logged."""

    pipeline_id = "native_llm"

    def __init__(self, client: ChatClient, executor: ToolExecutor, serialization: SerializationConfig,
                 retry: RetryPolicy = RetryPolicy()) -> None:
        self.client = client
        self.executor = executor
        self.serialization = serialization
        self.retry = retry

    def describe(self) -> dict[str, Any]:
        cfg = self.client.config
        return {
            "selector_id": "native_llm",
            "selector_model": f"{cfg.provider}/{cfg.model}",
            "argument_model": f"{cfg.provider}/{cfg.model}",
            "llm_config": thaw(cfg),
            "native_single_call": True,
            "prompt_version": PROMPT_VERSION,
        }

    def llm_configs(self) -> Sequence[LLMConfig]:
        return [self.client.config]

    async def run(self, task: Task, *, order_seed: int | None, id_seed: int | None) -> PipelineOutcome:
        try:
            cset = present_task(task, self.serialization, order_seed=order_seed, id_seed=id_seed)
            tools = build_native_tools(cset)
        except SerializationError as exc:
            return presentation_failure(self.pipeline_id, exc)

        request = ChatRequest(
            system=NATIVE_SYSTEM_PROMPT,
            user=render_state(task.state),
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
        )
        response, exc, attempts = await call_with_retry(lambda: self.client.complete(request), self.retry)
        latency = total_latency(attempts)
        inputs = {"selection_and_arguments": {"request": thaw(request), "provider_payload": response.request_payload if response else None}}

        if response is None:
            selection = error_selection(ErrorInfo("selection", error_kind(exc), str(exc)), latency_ms=latency,
                                        attempts=attempts, raw=getattr(exc, "raw", None))
            return PipelineOutcome(self.pipeline_id, cset, selection, SKIPPED_ARGUMENTS, None, inputs)

        raw = {"tool_calls": [thaw(c) for c in response.tool_calls], "text": response.text, "provider": response.raw}

        def selection_with(status: SelectionStatus, cid: str | None = None, error: ErrorInfo | None = None) -> SelectionResult:
            return SelectionResult(
                status=status,
                selected_candidate_id=cid,
                selected_tool_key=cset.by_id(cid).tool.key if cid else None,
                probabilities=None,
                probability_kind=ProbabilityKind.NONE,
                probability_issues=(),
                confidence=None,
                raw_response=raw,
                latency_ms=latency,
                usage=response.usage,
                model_reported=response.model_reported,
                error=error,
                attempts=attempts,
                provider_meta=response.provider_meta,
            )

        calls = response.tool_calls
        if not calls:
            return PipelineOutcome(self.pipeline_id, cset, selection_with(SelectionStatus.ABSTAINED), SKIPPED_ARGUMENTS, None, inputs)
        if len(calls) > 1:
            err = ErrorInfo("selection", "multiple_tool_calls", f"{len(calls)} tool calls in a single-choice task")
            return PipelineOutcome(self.pipeline_id, cset, selection_with(SelectionStatus.MULTIPLE, error=err), SKIPPED_ARGUMENTS, None, inputs)

        call = calls[0]
        by_name = {t.function_name: t for t in tools}
        if call.name not in by_name:
            err = ErrorInfo("selection", "invalid_tool_name", f"Model called unknown tool {call.name!r}")
            return PipelineOutcome(self.pipeline_id, cset, selection_with(SelectionStatus.ERROR, error=err), SKIPPED_ARGUMENTS, None, inputs)

        tool_def = by_name[call.name]
        selection = selection_with(SelectionStatus.SELECTED, tool_def.candidate_id)
        # Arguments came from the same call: latency and usage are attributed to selection only.
        arguments = arguments_from_call(call, tool_def, raw=raw, latency_ms=None, usage=None)
        arguments = dataclasses.replace(arguments, provider_meta=response.provider_meta)
        execution = await execute_if_ready(self.executor, task, selection, arguments)
        return PipelineOutcome(self.pipeline_id, cset, selection, arguments, execution, inputs)
