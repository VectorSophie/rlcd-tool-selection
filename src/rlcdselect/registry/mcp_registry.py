"""Tool registry backed by MCP servers, through the official MCP Python SDK (`mcp==2.3.0`).

One `mcp.Client` per server. `tools/list` is walked page by page with client-side caching off, and
every tool is normalized into the project's `ToolSpec` by the same function the static registry
uses (`tool_from_dict`), so equivalent static and MCP definitions compare equal.

Normalization preserves, exactly:
- server identity: the `server_id` the registry was configured with (MCP servers do not carry a
  stable id of their own; `serverInfo.name` is recorded separately);
- the tool name, never rewritten;
- the description (`""` when absent, as for static tools);
- the input schema, with its key order;
- annotations, in MCP wire form (camelCase, unset fields omitted).

The complete listing entry (title, outputSchema, icons, `_meta`, ...) stays available through
`raw_tool(key)`. Duplicate tool names *within one server* are an error. The same name on two
servers is two tools with different keys (`server/name`); presentation is left to the configured
`NamePolicy`, and nothing is merged.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import Client

from rlcdselect.core.types import ToolSpec
from rlcdselect.registry.static import tool_from_dict

MAX_LIST_PAGES = 100  # a server that paginates forever must not hang the registry


class MCPRegistryError(RuntimeError):
    pass


def tool_from_mcp(server_id: str, tool: Any) -> ToolSpec:
    """Normalize one `mcp_types.Tool` into a `ToolSpec`."""
    wire = tool.model_dump(by_alias=True, exclude_none=True, mode="json")
    return tool_from_dict({
        "server_id": server_id,
        "name": wire["name"],
        "description": wire.get("description"),
        "inputSchema": tool.input_schema,  # the server's own dict, key order intact
        "annotations": wire.get("annotations"),
    })


def _single_leaf(group: BaseExceptionGroup) -> BaseException | None:
    leaves: list[BaseException] = []
    stack: list[BaseException] = [group]
    while stack:
        exc = stack.pop()
        if isinstance(exc, BaseExceptionGroup):
            stack.extend(exc.exceptions)
        else:
            leaves.append(exc)
    return leaves[0] if len(leaves) == 1 else None


class MCPToolRegistry:
    """`ToolRegistry` over live MCP connections. Use `MCPToolRegistry.connect(...)`."""

    def __init__(self, clients: Mapping[str, Client]) -> None:
        self._clients = dict(clients)
        self._tools: tuple[ToolSpec, ...] | None = None
        self._by_key: dict[str, ToolSpec] = {}
        self._raw: dict[str, dict[str, Any]] = {}

    @classmethod
    @asynccontextmanager
    async def connect(cls, servers: Mapping[str, Any], *,
                      read_timeout_seconds: float | None = None) -> AsyncIterator["MCPToolRegistry"]:
        """Connect to every server and list its tools. `servers` maps a server id to anything
        `mcp.Client` accepts: a URL (Streamable HTTP), `StdioServerParameters`, a `Transport`, or
        an in-process `Server`/`MCPServer`."""
        try:
            async with AsyncExitStack() as stack:
                clients = {}
                for server_id, target in servers.items():
                    if not server_id or "/" in server_id:
                        raise MCPRegistryError(f"Invalid server id {server_id!r}")
                    client = Client(target, cache=None, read_timeout_seconds=read_timeout_seconds)
                    clients[server_id] = await stack.enter_async_context(client)
                registry = cls(clients)
                await registry.refresh()
                yield registry
        except BaseExceptionGroup as group:
            # The SDK's task groups wrap any exception raised inside this context, e.g. a
            # FatalRunError from the runner, in nested ExceptionGroups. Re-raise a single
            # underlying error unchanged so callers' `except FatalRunError` keeps working.
            leaf = _single_leaf(group)
            if leaf is None:
                raise
            raise leaf from None

    async def refresh(self) -> tuple[ToolSpec, ...]:
        tools, by_key, raw = [], {}, {}
        for server_id, client in self._clients.items():
            names = set()
            cursor = None
            for _ in range(MAX_LIST_PAGES):
                page = await client.list_tools(cursor=cursor, cache_mode="refresh")
                for t in page.tools:
                    if t.name in names:
                        raise MCPRegistryError(f"Server {server_id!r} lists tool {t.name!r} more than once")
                    names.add(t.name)
                    spec = tool_from_mcp(server_id, t)
                    tools.append(spec)
                    by_key[spec.key] = spec
                    raw[spec.key] = t.model_dump(by_alias=True, exclude_none=True, mode="json")
                cursor = page.next_cursor
                if cursor is None:
                    break
            else:
                raise MCPRegistryError(f"Server {server_id!r}: tools/list did not finish in {MAX_LIST_PAGES} pages")
        self._tools, self._by_key, self._raw = tuple(tools), by_key, raw
        return self._tools

    async def list_tools(self) -> tuple[ToolSpec, ...]:
        return self._tools if self._tools is not None else await self.refresh()

    def get(self, key: str) -> ToolSpec:
        return self._by_key[key]

    def raw_tool(self, key: str) -> dict[str, Any]:
        """The full MCP listing entry for a tool (wire form)."""
        return self._raw[key]

    def client_for(self, server_id: str) -> Client:
        return self._clients[server_id]

    def server_info(self, server_id: str) -> dict[str, Any] | None:
        info = self._clients[server_id].server_info
        return info.model_dump(by_alias=True, exclude_none=True, mode="json") if info else None

    @property
    def server_ids(self) -> tuple[str, ...]:
        return tuple(self._clients)
