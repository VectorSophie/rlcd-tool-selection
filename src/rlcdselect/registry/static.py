from collections.abc import Iterable, Mapping
from typing import Any

from rlcdselect.core.types import ToolSpec


def tool_from_dict(data: Mapping[str, Any]) -> ToolSpec:
    """Normalize an MCP-style tool dict (`name`, `description`, `inputSchema`/`input_schema`, `annotations`)."""
    schema = data.get("input_schema", data.get("inputSchema"))
    if schema is None:
        raise ValueError(f"Tool {data.get('name')!r} has no input schema")
    return ToolSpec(
        server_id=str(data["server_id"]),
        name=str(data["name"]),
        description=str(data.get("description") or ""),
        input_schema=schema,
        annotations=data.get("annotations"),
    )


class StaticToolRegistry:
    """An in-memory registry for offline experiments."""

    def __init__(self, tools: Iterable[ToolSpec]) -> None:
        self._tools = tuple(tools)
        keys = [t.key for t in self._tools]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate tool keys in registry: {keys}")
        self._by_key = {t.key: t for t in self._tools}

    @classmethod
    def from_dicts(cls, items: Iterable[Mapping[str, Any]]) -> "StaticToolRegistry":
        return cls(tool_from_dict(item) for item in items)

    async def list_tools(self) -> tuple[ToolSpec, ...]:
        return self._tools

    def get(self, key: str) -> ToolSpec:
        return self._by_key[key]
