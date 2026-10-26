import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from jsonschema import Draft202012Validator

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import ErrorInfo, ToolExecutionResult, ToolSpec

Handler = Callable[[Mapping[str, Any]], Any]


def schema_errors(schema: Mapping[str, Any], arguments: Mapping[str, Any]) -> tuple[str, ...]:
    validator = Draft202012Validator(thaw(schema))
    return tuple(sorted(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in validator.iter_errors(thaw(arguments))))


# Values a model writes when the request lacks the information, e.g. "<UNKNOWN>" or "[RECIPIENT]".
# A real tool would act on them (an email to "<UNKNOWN>"), so the mock refuses them as an outcome.
_PLACEHOLDER = re.compile(
    r"<[^<>]{1,40}>|\[[A-Z0-9 _-]{1,40}\]|\{\{[^{}]{1,40}\}\}|(?i:unknown|tbd|todo|placeholder|n/a)")


def placeholder_values(value: Any, path: str = "") -> tuple[str, ...]:
    """Paths of string values that are entirely a placeholder."""
    if isinstance(value, str):
        return (path or "<root>",) if _PLACEHOLDER.fullmatch(value.strip()) else ()
    if isinstance(value, Mapping):
        return tuple(p for k, v in value.items() for p in placeholder_values(v, f"{path}/{k}" if path else str(k)))
    if isinstance(value, (list, tuple)):
        return tuple(p for i, v in enumerate(value) for p in placeholder_values(v, f"{path}/{i}" if path else str(i)))
    return ()


class MockExecutor:
    """Validates arguments against the tool's schema, then returns a canned or handler-computed result.

    Calls are recorded in `calls`. Handlers raising exceptions become execution errors, not crashes.
    Schema-valid arguments that are placeholders fail as `placeholder_arguments`.
    """

    def __init__(self, handlers: Mapping[str, Handler] | None = None) -> None:
        self._handlers = dict(handlers or {})
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, tool: ToolSpec, arguments: Mapping[str, Any]) -> ToolExecutionResult:
        start = time.perf_counter()
        args = thaw(arguments)
        self.calls.append((tool.key, args))
        errors = schema_errors(tool.input_schema, args)
        if errors:
            return ToolExecutionResult(
                False, None, ErrorInfo("execution", "invalid_arguments", "; ".join(errors)), _ms(start)
            )
        placeholders = placeholder_values(args)
        if placeholders:
            return ToolExecutionResult(False, None, ErrorInfo(
                "execution", "placeholder_arguments", f"Placeholder values at {list(placeholders)}"), _ms(start))
        handler = self._handlers.get(tool.key)
        try:
            output = handler(args) if handler else {"ok": True, "tool": tool.key, "arguments": args}
        except Exception as exc:  # a failing tool is an outcome to record, not a harness crash
            return ToolExecutionResult(False, None, ErrorInfo("execution", "tool_error", repr(exc)), _ms(start))
        return ToolExecutionResult(True, output, None, _ms(start))


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
