"""Deterministic local MCP servers that serve the static fixture tools. No network.

`fixture_servers()` builds one low-level `mcp.server.Server` per fixture `server_id` (`web`,
`mail`, `mail-relay`, ...), exposing exactly the fixture's tool definitions: the same names,
descriptions and JSON schemas, so the MCP-backed registry normalizes to the same `ToolSpec`s as
the static registry. The low-level server is used, not `MCPServer`, because `MCPServer` derives
input schemas from Python signatures and would not reproduce the fixture schemas byte for byte.

Handlers are deterministic functions of the arguments (no clocks, no randomness, no I/O). A
handler raising `ToolFailure` returns an MCP tool error (`isError: true`); any other exception
becomes a JSON-RPC error, as the SDK does for a failing handler. Each server records the calls it
received in `server_calls[server_id]`, so tests can check routing.

Run one server over stdio (used by the subprocess transport test):

    python -m rlcdselect.datasets.mcp_fixture_server mail
"""

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

import mcp_types as types
from mcp.server import Server

from rlcdselect.datasets.fixtures import DEFAULT_FIXTURE, load_fixture_data

Handler = Callable[[dict[str, Any]], Any]


class ToolFailure(Exception):
    """Raised by a fixture handler to return an MCP tool error (isError) instead of a result."""


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]


def _search(args: dict[str, Any]) -> dict[str, Any]:
    n = min(int(args.get("max_results", 3)), 3)
    return {"results": [{"title": f"Result {i + 1} for {args['query']}", "id": _digest([args["query"], i])}
                        for i in range(n)]}


def _send(args: dict[str, Any]) -> dict[str, Any]:
    return {"status": "sent", "message_id": _digest(args), "recipients": list(args["to"])}


def _draft(args: dict[str, Any]) -> dict[str, Any]:
    return {"status": "drafted", "draft_id": _digest(args)}


def _calendar(args: dict[str, Any]) -> dict[str, Any]:
    if args["end_date"] < args["start_date"]:
        raise ToolFailure("end_date is before start_date")
    return {"events": [{"title": "Standup", "date": args["start_date"]}]}


def _weather(args: dict[str, Any]) -> dict[str, Any]:
    return {"city": args["city"], "forecast": "clear", "high_c": 21}


DEFAULT_HANDLERS: dict[str, Handler] = {
    "search_web": _search, "search_web_pro": _search, "search_web_results": _search, "lookup_web": _search,
    "search_repository": _search, "send_email": _send, "send_mail": _send, "create_email_draft": _draft,
    "calendar_lookup": _calendar, "weather_forecast": _weather,
}


def build_server(server_id: str, tools: list[Mapping[str, Any]], handlers: Mapping[str, Handler] | None = None,
                 calls: list | None = None) -> Server:
    """A low-level MCP server exposing `tools` (fixture dicts) with deterministic handlers."""
    handlers = {**DEFAULT_HANDLERS, **(handlers or {})}
    listing = [
        types.Tool(name=t["name"], description=t.get("description"), input_schema=dict(t["input_schema"]),
                   annotations=types.ToolAnnotations.model_validate(t["annotations"]) if t.get("annotations") else None)
        for t in tools
    ]
    names = {t.name for t in listing}

    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=listing)

    async def on_call_tool(ctx, params) -> types.CallToolResult:
        args = dict(params.arguments or {})
        if calls is not None:
            calls.append((params.name, args))
        if params.name not in names:
            return _error(f"Unknown tool {params.name!r}")
        handler = handlers.get(params.name)
        if handler is None:
            return _error(f"No fixture handler for {params.name!r}")
        try:
            output = handler(args)
        except ToolFailure as exc:
            return _error(str(exc))
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(output))],
                                    structured_content=output)

    return Server(server_id, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


def fixture_servers(name: str = DEFAULT_FIXTURE, handlers: Mapping[str, Handler] | None = None,
                    server_calls: dict[str, list] | None = None) -> dict[str, Server]:
    """One in-process server per fixture server id, in fixture order."""
    by_server: dict[str, list] = defaultdict(list)
    for t in load_fixture_data(name)["tools"]:
        by_server[t["server_id"]].append(t)
    if server_calls is not None:
        for sid in by_server:
            server_calls.setdefault(sid, [])
    return {sid: build_server(sid, tools, handlers, server_calls[sid] if server_calls is not None else None)
            for sid, tools in by_server.items()}


async def _serve_stdio(server_id: str) -> None:
    from mcp.server.stdio import stdio_server

    server = fixture_servers()[server_id]
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("server_id")
    asyncio.run(_serve_stdio(parser.parse_args().server_id))
