"""The shared argument generator used by every decomposed arm.

It receives exactly one tool, the one already selected, and is forced to call it. A response that
calls any other tool is recorded as a `tool_mismatch` error; the generator can never change the
selection.
"""

from collections.abc import Mapping
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.prompts import ARGUMENT_SYSTEM_PROMPT
from rlcdselect.core.retry import call_with_retry, error_kind, total_latency
from rlcdselect.core.serialization import Candidate, NativeToolDef, native_tool_def, render_state
from rlcdselect.core.types import ArgumentResult, ArgumentStatus, AttemptLog, ErrorInfo, RetryPolicy, Usage
from rlcdselect.execution.mock import schema_errors
from rlcdselect.llm.base import ChatClient, ChatRequest, ChatResponse, ForcedTool, ToolCall


def arguments_from_call(
    call: ToolCall,
    tool_def: NativeToolDef,
    *,
    raw: Any,
    latency_ms: float | None,
    usage: Usage | None,
    attempts: tuple[AttemptLog, ...] = (),
) -> ArgumentResult:
    """Turn one tool call into an ArgumentResult, validating against the tool's schema."""
    if call.arguments is None:
        return ArgumentResult(
            ArgumentStatus.ERROR, None, None, (), raw, latency_ms, usage,
            ErrorInfo("arguments", "invalid_json", f"Unparseable arguments: {call.raw_arguments!r}"), attempts,
        )
    errors = schema_errors(tool_def.parameters, call.arguments)
    return ArgumentResult(ArgumentStatus.OK, thaw(call.arguments), not errors, errors, raw, latency_ms, usage, None, attempts)


class ArgumentGenerator:
    def __init__(self, client: ChatClient, retry: RetryPolicy = RetryPolicy()) -> None:
        self.client = client
        self.retry = retry
        self.last_request: ChatRequest | None = None

    def build_request(self, state: Mapping[str, Any], candidate: Candidate) -> ChatRequest:
        tool_def = native_tool_def(candidate)
        return ChatRequest(
            system=ARGUMENT_SYSTEM_PROMPT,
            user=render_state(state),
            tools=(tool_def,),
            tool_choice=ForcedTool(tool_def.function_name),
            parallel_tool_calls=False,
        )

    async def generate(self, state: Mapping[str, Any], candidate: Candidate) -> tuple[ArgumentResult, ChatRequest, Any]:
        """Returns (result, request sent, provider payload sent or None)."""
        request = self.build_request(state, candidate)
        assert len(request.tools) == 1  # structural invariant: one tool, never the candidate set
        tool_def = request.tools[0]
        response, exc, attempts = await call_with_retry(lambda: self.client.complete(request), self.retry)
        latency = total_latency(attempts)
        if response is None:
            err = ErrorInfo("arguments", error_kind(exc), str(exc))
            raw = getattr(exc, "raw", None)
            return ArgumentResult(ArgumentStatus.ERROR, None, None, (), raw, latency, None, err, attempts), request, None
        return self._interpret(response, tool_def, latency, attempts), request, response.request_payload

    @staticmethod
    def _interpret(response: ChatResponse, tool_def: NativeToolDef, latency: float, attempts: tuple[AttemptLog, ...]) -> ArgumentResult:
        raw = {"tool_calls": [thaw(c) for c in response.tool_calls], "text": response.text, "provider": response.raw}

        def error(kind: str, message: str) -> ArgumentResult:
            return ArgumentResult(
                ArgumentStatus.ERROR, None, None, (), raw, latency, response.usage,
                ErrorInfo("arguments", kind, message), attempts,
            )

        if not response.tool_calls:
            return error("no_tool_call", "The argument model returned no tool call")
        if len(response.tool_calls) > 1:
            return error("multiple_tool_calls", f"{len(response.tool_calls)} tool calls returned")
        call = response.tool_calls[0]
        if call.name != tool_def.function_name:
            return error("tool_mismatch", f"Selected {tool_def.function_name!r} but the argument model called {call.name!r}")
        return arguments_from_call(call, tool_def, raw=raw, latency_ms=latency, usage=response.usage, attempts=attempts)
