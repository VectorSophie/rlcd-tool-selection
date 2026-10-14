from collections.abc import Mapping
from typing import Any, Protocol

from rlcdselect.core.types import ToolExecutionResult, ToolSpec


class ToolExecutor(Protocol):
    async def call_tool(self, tool: ToolSpec, arguments: Mapping[str, Any]) -> ToolExecutionResult:
        """Execute one call. Failures are returned as results, never raised."""
        ...
