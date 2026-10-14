import pytest
from conftest import run

from rlcdselect.core.types import Task, ToolRole
from rlcdselect.registry.static import StaticToolRegistry, tool_from_dict

SCHEMA = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}


def test_mcp_style_and_internal_dicts_normalize_identically():  # required test 7 (static side)
    mcp_style = {"server_id": "s", "name": "t", "description": "d", "inputSchema": SCHEMA, "annotations": {"readOnlyHint": True}}
    internal = {"server_id": "s", "name": "t", "description": "d", "input_schema": SCHEMA, "annotations": {"readOnlyHint": True}}
    assert tool_from_dict(mcp_style) == tool_from_dict(internal)
    assert tool_from_dict({"server_id": "s", "name": "t", "inputSchema": SCHEMA}).description == ""
    with pytest.raises(ValueError):
        tool_from_dict({"server_id": "s", "name": "t"})


def test_registry_rejects_duplicate_keys():
    tool = tool_from_dict({"server_id": "s", "name": "t", "input_schema": SCHEMA})
    with pytest.raises(ValueError):
        StaticToolRegistry([tool, tool])
    assert run(StaticToolRegistry([tool]).list_tools()) == (tool,)


def test_fixtures_cover_required_scenarios(fixtures):
    _, tasks = fixtures
    tags = {tag for t in tasks for tag in t.tags}
    assert {"obvious", "similar_tools", "no_suitable_tool", "missing_information",
            "trusted_vs_attacker", "trusted_vs_attacker_vs_decoy"} <= tags
    roles = {r for t in tasks for r in t.roles.values()}
    assert roles == set(ToolRole)


def test_fixture_gold_positions_vary(fixtures):
    """Guard against the MetaTool-style artifact where gold is always listed first."""
    _, tasks = fixtures
    positions = {next(i for i, tool in enumerate(t.tools) if tool.key in t.expected.tool_keys)
                 for t in tasks if not t.expected.expects_abstention}
    assert len(positions) >= 3


def test_task_validation(fixtures):
    _, tasks = fixtures
    task = tasks[0]
    with pytest.raises(ValueError):
        Task(task.task_id, task.state, task.tools, task.expected, roles={})
