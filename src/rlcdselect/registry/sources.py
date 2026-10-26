"""Choosing where an experiment's tools come from: the static fixture registry or MCP servers.

With MCP, tasks keep their ids, state and ground truth, but every tool definition is replaced by
the one the owning MCP server lists (`rebind_tasks`). A task whose tool is not listed is an error;
nothing is substituted. Definitions that differ from the task's original (static) ones are
reported, so a server that drifted from the fixture is visible before any model call.
"""

import dataclasses
import shlex
from collections.abc import Sequence
from typing import Any

from mcp import StdioServerParameters

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import Task
from rlcdselect.registry.mcp_registry import MCPToolRegistry


class ToolSourceError(ValueError):
    pass


def rebind_tasks(tasks: Sequence[Task], registry: MCPToolRegistry) -> tuple[tuple[Task, ...], list[dict[str, Any]]]:
    """Tasks with tool definitions taken from `registry`, plus a list of definition differences."""
    rebound, diffs, missing = [], [], []
    for task in tasks:
        tools = []
        for tool in task.tools:
            try:
                listed = registry.get(tool.key)
            except KeyError:
                missing.append(f"{task.task_id}: {tool.key}")
                continue
            if listed != tool:
                diffs.append({"task_id": task.task_id, "tool": tool.key,
                              "fields": [f for f in ("description", "input_schema", "annotations")
                                         if thaw(getattr(listed, f)) != thaw(getattr(tool, f))]})
            tools.append(listed)
        if len(tools) == len(task.tools):  # rebuilt only when complete; missing tools are reported below
            rebound.append(dataclasses.replace(task, tools=tuple(tools)))
    if missing:
        raise ToolSourceError(f"{len(missing)} task tool(s) not listed by any configured MCP server: {missing[:5]}")
    return tuple(rebound), diffs


def parse_stdio_server(spec: str) -> tuple[str, StdioServerParameters]:
    """`server_id=command arg ...` → (server_id, parameters for a local stdio MCP server)."""
    server_id, sep, command = spec.partition("=")
    parts = shlex.split(command)
    if not sep or not server_id or not parts:
        raise ToolSourceError(f"Expected SERVER_ID=COMMAND [ARGS...], got {spec!r}")
    return server_id, StdioServerParameters(command=parts[0], args=parts[1:])
