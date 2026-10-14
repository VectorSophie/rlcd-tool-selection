from typing import Protocol

from rlcdselect.core.types import ToolSpec


class ToolRegistry(Protocol):
    async def list_tools(self) -> tuple[ToolSpec, ...]: ...
