"""Tool execution through MCP `tools/call`, via the official MCP Python SDK.

The executor calls exactly one tool on exactly one server: the server that listed the selected
`ToolSpec`. Before any call it checks that the tool is listed and that the selected spec is
identical to the server's listing, then validates the arguments against the input schema
(low-level MCP servers do not validate arguments themselves).

It uses `client.session.call_tool(..., allow_input_required=True)`, which sends one `tools/call`
request and nothing else, rather than `Client.call_tool`, because `Client.call_tool` (mcp 2.3.0):
- re-lists tools and **resends the call once** after a `HEADER_MISMATCH` error, and
- answers server input requests (sampling/elicitation) and **retries automatically**.
Both would be silent retries. Here they surface as execution errors. The only retries are the
harness's explicit `RetryPolicy`, applied to timeouts (`TransientError`) and logged per attempt.

Failures are returned as results, never raised, each attributed to the `execution` stage:

| kind | cause |
|---|---|
| `tool_not_listed` | the selected tool's server does not list it |
| `tool_definition_mismatch` | the selected `ToolSpec` differs from the server's current listing |
| `invalid_arguments` | arguments fail the input schema; no call is made |
| `tool_error` | the tool ran and returned `isError: true` |
| `mcp_error` | a protocol-level error (JSON-RPC error, e.g. the handler raised) |
| `mcp_input_required` | the server asked for input mid-call; not answered |
| `mcp_invalid_result` | the result failed the tool's output schema or the protocol shape |
| `transient` | timeouts, after the explicit retry policy is exhausted |
"""

import time
from collections.abc import Mapping
from typing import Any

import mcp_types
from mcp import MCPError
from pydantic import ValidationError

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.retry import call_with_retry, error_kind
from rlcdselect.core.types import (
    ErrorInfo,
    ProviderError,
    RetryPolicy,
    ToolExecutionResult,
    ToolSpec,
    TransientError,
)
from rlcdselect.execution.mock import schema_errors
from rlcdselect.registry.mcp_registry import MCPToolRegistry


class MCPExecutor:
    def __init__(self, registry: MCPToolRegistry, *, retry: RetryPolicy = RetryPolicy(),
                 read_timeout_seconds: float | None = None) -> None:
        self.registry = registry
        self.retry = retry
        self.read_timeout_seconds = read_timeout_seconds
        self.calls: list[tuple[str, dict[str, Any]]] = []  # (tool key, arguments) actually sent

    async def call_tool(self, tool: ToolSpec, arguments: Mapping[str, Any]) -> ToolExecutionResult:
        start = time.perf_counter()
        args = thaw(arguments)
        meta: dict[str, Any] = {"executor": "mcp", "server_id": tool.server_id, "tool_name": tool.name}

        def fail(kind: str, message: str, attempts=(), **extra) -> ToolExecutionResult:
            return ToolExecutionResult(False, None, ErrorInfo("execution", kind, message), _ms(start),
                                       tuple(attempts), {**meta, **extra})

        try:
            listed = self.registry.get(tool.key)
        except KeyError:
            return fail("tool_not_listed", f"{tool.key} is not listed by MCP server {tool.server_id!r}")
        if listed != tool:
            return fail("tool_definition_mismatch", f"Selected definition of {tool.key} differs from the server's listing")
        errors = schema_errors(tool.input_schema, args)
        if errors:
            return fail("invalid_arguments", "; ".join(errors))

        client = self.registry.client_for(tool.server_id)
        meta["protocol_version"] = client.protocol_version

        async def once() -> Any:
            self.calls.append((tool.key, args))
            try:
                return await client.session.call_tool(tool.name, args, read_timeout_seconds=self.read_timeout_seconds,
                                                      allow_input_required=True)
            except MCPError as exc:
                if exc.code == mcp_types.REQUEST_TIMEOUT:
                    raise TransientError(f"MCP request timed out: {exc}") from exc
                raise ProviderError("mcp_error", str(exc), raw={"code": exc.code, "message": str(exc)}) from exc
            except (ValidationError, RuntimeError) as exc:  # output-schema or protocol-shape failures
                raise ProviderError("mcp_invalid_result", str(exc)) from exc

        result, exc, attempts = await call_with_retry(once, self.retry)
        if result is None:
            return fail(error_kind(exc), str(exc), attempts, error_detail=getattr(exc, "raw", None))
        if isinstance(result, mcp_types.InputRequiredResult):
            return fail("mcp_input_required", "Server requested input during tools/call; not answered", attempts,
                        result=result.model_dump(by_alias=True, exclude_none=True, mode="json"))

        output = {
            "content": [c.model_dump(by_alias=True, exclude_none=True, mode="json") for c in result.content],
            "structured_content": thaw(result.structured_content),
        }
        meta["is_error"] = bool(result.is_error)
        if result.is_error:
            text = " ".join(c.get("text", "") for c in output["content"] if c.get("type") == "text")
            return ToolExecutionResult(False, output, ErrorInfo("execution", "tool_error", text or "isError"),
                                       _ms(start), tuple(attempts), meta)
        return ToolExecutionResult(True, output, None, _ms(start), tuple(attempts), meta)


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
