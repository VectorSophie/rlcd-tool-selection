"""MCP-backed registry and executor (official SDK), against deterministic local fixture servers.

No network: servers run in-process, except one test that starts a fixture server as a local
subprocess over stdio to exercise a real transport.
"""

import json
import sys

import mcp_types as types
import pytest
from conftest import run
from helpers import call, response
from mcp import MCPError, StdioServerParameters

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import present_task
from rlcdselect.core.types import FatalRunError, RetryPolicy, ToolSpec
from rlcdselect.datasets.fixtures import load_fixture_data, load_fixtures
from rlcdselect.datasets.mcp_fixture_server import build_server, fixture_servers
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mcp_executor import MCPExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import ScriptedChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.registry.mcp_registry import MCPRegistryError, MCPToolRegistry, tool_from_mcp
from rlcdselect.registry.static import tool_from_dict
from rlcdselect.selectors.mock import ScriptedSelector, output

SEND = {"to": ["dave@example.com"], "subject": "Report", "body": "The report is ready."}


def with_registry(fn, servers=None, **kwargs):
    async def main():
        async with MCPToolRegistry.connect(servers if servers is not None else fixture_servers(), **kwargs) as reg:
            return await fn(reg)
    return run(main())


# --- registry -----------------------------------------------------------------------------------

def test_mcp_and_static_registries_normalize_to_the_same_tool_specs():  # required test 7, MCP side
    static, _ = load_fixtures()

    async def body(reg):
        return await reg.list_tools()

    mcp_tools = with_registry(body)
    static_tools = run(static.list_tools())
    assert sorted(mcp_tools, key=lambda t: t.key) == sorted(static_tools, key=lambda t: t.key)
    for t in mcp_tools:  # schema key order survives the protocol round trip
        assert json.dumps(thaw(t.input_schema)) == json.dumps(thaw(static.get(t.key).input_schema))


def test_normalization_preserves_identity_name_description_schema_annotations():
    tool = types.Tool(name="Weird.Name-v2", description=None,
                      input_schema={"type": "object", "properties": {"z": {"type": "string"}, "a": {"type": "integer"}}},
                      annotations=types.ToolAnnotations(read_only_hint=True), title="Shown title")
    server = build_server("s1", [{"name": "Weird.Name-v2", "description": None, "input_schema": tool.input_schema,
                                  "annotations": {"readOnlyHint": True}}])

    async def body(reg):
        spec = reg.get("s1/Weird.Name-v2")
        return spec, reg.raw_tool("s1/Weird.Name-v2"), reg.server_info("s1")

    spec, raw, info = with_registry(body, {"s1": server})
    assert spec == ToolSpec("s1", "Weird.Name-v2", "", tool.input_schema, {"readOnlyHint": True})
    assert list(spec.input_schema["properties"]) == ["z", "a"]
    assert raw["name"] == "Weird.Name-v2" and raw["inputSchema"] == tool.input_schema
    assert info["name"] == "s1"
    assert tool_from_mcp("s1", tool) == tool_from_dict({"server_id": "s1", "name": "Weird.Name-v2",
                                                        "inputSchema": tool.input_schema,
                                                        "annotations": {"readOnlyHint": True}})


def test_same_tool_name_on_two_servers_is_kept_apart():
    async def body(reg):
        return [t.key for t in await reg.list_tools() if t.name == "send_email"]

    assert with_registry(body) == ["mail/send_email", "mail-relay/send_email"]  # not merged, not renamed


def test_duplicate_name_within_one_server_is_an_error():
    tool = {"name": "dup", "description": "", "input_schema": {"type": "object"}}
    with pytest.raises(MCPRegistryError, match="more than once"):
        with_registry(lambda reg: None, {"s": build_server("s", [tool, tool])})
    with pytest.raises(MCPRegistryError, match="Invalid server id"):
        with_registry(lambda reg: None, {"a/b": build_server("x", [tool])})


def test_paginated_listing_is_walked():
    from mcp.server import Server

    pages = {None: (["a", "b"], "p2"), "p2": (["c"], None)}

    async def on_list_tools(ctx, params):
        names, nxt = pages[params.cursor if params else None]
        return types.ListToolsResult(tools=[types.Tool(name=n, input_schema={"type": "object"}) for n in names],
                                     next_cursor=nxt)

    async def body(reg):
        return [t.name for t in await reg.list_tools()]

    assert with_registry(body, {"p": Server("p", on_list_tools=on_list_tools)}) == ["a", "b", "c"]


# --- executor -----------------------------------------------------------------------------------

def test_call_tool_routes_to_the_owning_server_only():
    calls = {}

    async def body(reg):
        ex = MCPExecutor(reg)
        relay = await ex.call_tool(reg.get("mail-relay/send_email"), SEND)
        direct = await ex.call_tool(reg.get("mail/send_email"), SEND)
        return relay, direct

    relay, direct = with_registry(body, fixture_servers(server_calls=calls))
    assert relay.success and direct.success
    assert relay.meta["server_id"] == "mail-relay" and direct.meta["server_id"] == "mail"
    assert relay.output["structured_content"]["status"] == "sent"
    assert calls["mail-relay"] == [("send_email", SEND)] and calls["mail"] == [("send_email", SEND)]
    assert all(v == [] for k, v in calls.items() if k not in ("mail", "mail-relay"))


def test_invalid_arguments_are_rejected_before_any_call():
    calls = {}

    async def body(reg):
        return await MCPExecutor(reg).call_tool(reg.get("mail/send_email"), {"to": "not-a-list", "subject": "x"})

    result = with_registry(body, fixture_servers(server_calls=calls))
    assert not result.success and result.error.stage == "execution" and result.error.kind == "invalid_arguments"
    assert calls["mail"] == []


def test_tool_error_and_protocol_error_are_distinct_execution_errors():
    def explode(args):
        raise RuntimeError("handler crashed")

    calls = {}

    async def body(reg):
        ex = MCPExecutor(reg, retry=RetryPolicy(max_attempts=3))
        tool_error = await ex.call_tool(reg.get("calendar/calendar_lookup"),
                                        {"start_date": "2026-10-22", "end_date": "2026-10-20"})
        protocol = await ex.call_tool(reg.get("web/search_web"), {"query": "x"})
        return tool_error, protocol

    tool_error, protocol = with_registry(body, fixture_servers(handlers={"search_web": explode}, server_calls=calls))
    assert tool_error.error.kind == "tool_error" and "before start_date" in tool_error.error.message
    assert tool_error.meta["is_error"] is True and tool_error.output["content"][0]["type"] == "text"
    assert protocol.error.kind == "mcp_error" and protocol.meta["error_detail"]["code"] == types.INTERNAL_ERROR
    assert len(calls["web"]) == 1  # a non-transient error is never retried, even with a retry budget
    assert len(protocol.attempts) == 1


def test_selected_tool_must_match_the_servers_listing():
    async def body(reg):
        ex = MCPExecutor(reg)
        listed = reg.get("web/search_web")
        altered = ToolSpec(listed.server_id, listed.name, "A different description.", listed.input_schema)
        unknown = ToolSpec("web", "not_there", "", {"type": "object"})
        return await ex.call_tool(altered, {"query": "x"}), await ex.call_tool(unknown, {})

    altered, unknown = with_registry(body)
    assert altered.error.kind == "tool_definition_mismatch"
    assert unknown.error.kind == "tool_not_listed"


class _Session:
    def __init__(self, steps):
        self.steps, self.calls = list(steps), 0

    async def call_tool(self, name, args, read_timeout_seconds=None, allow_input_required=False):
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class _Client:
    protocol_version = "test"

    def __init__(self, session):
        self.session = session


class _Registry:
    def __init__(self, tool, session):
        self.tool, self._client = tool, _Client(session)

    def get(self, key):
        return self.tool

    def client_for(self, server_id):
        return self._client


TOOL = ToolSpec("s", "t", "", {"type": "object"})


def test_timeouts_are_retried_only_under_the_explicit_policy():
    ok = types.CallToolResult(content=[types.TextContent(type="text", text="done")])
    timeout = MCPError(types.REQUEST_TIMEOUT, "timed out")

    session = _Session([timeout, ok])
    once = run(MCPExecutor(_Registry(TOOL, session)).call_tool(TOOL, {}))
    assert once.error.kind == "transient" and session.calls == 1  # default policy: one attempt

    session = _Session([timeout, ok])
    retried = run(MCPExecutor(_Registry(TOOL, session), retry=RetryPolicy(max_attempts=2)).call_tool(TOOL, {}))
    assert retried.success and session.calls == 2
    assert [a.error_kind for a in retried.attempts] == ["transient", None]  # every attempt logged


def test_input_requests_are_not_answered():
    session = _Session([types.InputRequiredResult(request_state="opaque")])
    result = run(MCPExecutor(_Registry(TOOL, session)).call_tool(TOOL, {}))
    assert result.error.kind == "mcp_input_required" and session.calls == 1


# --- pipeline integration -----------------------------------------------------------------------

def test_pipelines_run_end_to_end_over_mcp(fixtures, serialization, tmp_path):
    _, tasks = fixtures
    task = next(t for t in tasks if t.task_id == "attacker_near_name_collision")
    cset = present_task(task, serialization, order_seed=None, id_seed=None)
    send = next(c for c in cset.candidates if c.tool.key == "mail/send_email")
    calls = {}
    path = tmp_path / "r.jsonl"

    async def body(reg):
        executor = MCPExecutor(reg)
        native = NativePipeline(ScriptedChatClient([response(call(send.display_name, SEND))]), executor, serialization)
        decomposed = DecomposedPipeline(ScriptedSelector([output(send.candidate_id)]),
                                        ArgumentGenerator(ScriptedChatClient([response(call(send.display_name, SEND))])),
                                        executor, serialization)
        return await run_experiment([task], [native, decomposed], ExperimentConfig("mcp"), JsonlWriter(path, secrets=()))

    records = with_registry(body, fixture_servers(server_calls=calls))
    assert [r["task_success"] for r in records] == [True, True]
    assert [r["grounded_task_success"] for r in records] == [True, True]
    for rec in read_jsonl(path):
        assert rec["execution_meta"]["executor"] == "mcp" and rec["execution_meta"]["server_id"] == "mail"
        assert rec["execution_output"]["structured_content"]["status"] == "sent"
    assert calls["mail"] == [("send_email", SEND)] * 2 and calls["mailfast"] == []


def test_fatal_errors_inside_the_registry_context_are_not_wrapped():
    async def body(reg):
        raise FatalRunError("model_mismatch", "boom")

    with pytest.raises(FatalRunError, match="boom"):
        with_registry(body)


def test_stdio_subprocess_server_matches_static_definitions():
    """A real transport: the fixture server as a local subprocess over stdio."""
    static, _ = load_fixtures()
    params = StdioServerParameters(command=sys.executable, args=["-m", "rlcdselect.datasets.mcp_fixture_server", "mail"])

    async def body(reg):
        tools = await reg.list_tools()
        result = await MCPExecutor(reg).call_tool(reg.get("mail/send_email"), SEND)
        return tools, result

    tools, result = with_registry(body, {"mail": params}, read_timeout_seconds=30)
    expected = [t for t in load_fixture_data()["tools"] if t["server_id"] == "mail"]
    assert [t.key for t in tools] == [f"mail/{t['name']}" for t in expected]
    assert all(t == static.get(t.key) for t in tools)
    assert result.success and result.output["structured_content"]["recipients"] == SEND["to"]
