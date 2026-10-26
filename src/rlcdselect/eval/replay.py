"""Rebuild a run's inputs from its JSONL record alone, to check that records suffice for reproduction."""

from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.prompts import NATIVE_SYSTEM_PROMPT
from rlcdselect.core.serialization import (
    CriteriaFormat,
    NamePolicy,
    Representation,
    SerializationConfig,
    build_native_tools,
    build_selector_request,
    present_task,
    render_state,
)
from rlcdselect.core.types import ExpectedOutcome, Task, ToolRole, ToolSpec
from rlcdselect.llm.base import ChatRequest


def task_from_record(record: dict[str, Any]) -> Task:
    tools = tuple(
        ToolSpec(t["server_id"], t["name"], t["description"], t["input_schema"], t.get("annotations"))
        for t in record["tools_before"]
    )
    exp = record["expected"]
    return Task(
        task_id=record["task_id"],
        state=record["state"],
        tools=tools,
        expected=ExpectedOutcome(frozenset(exp["tool_keys"]), exp["abstain_reason"], exp["argument_constraints"],
                                 exp.get("argument_options")),
        roles={k: ToolRole(v) for k, v in record["roles"].items()},
        tags=tuple(record["task_tags"]),
        argument_grounding=exp.get("argument_grounding"),  # absent before record schema v3
        evaluation_context=exp.get("evaluation_context"),
        provenance=record.get("task_provenance"),
    )


def serialization_from_record(record: dict[str, Any]) -> SerializationConfig:
    s = record["serialization"]
    return SerializationConfig(
        representation=Representation(s["representation"]),
        name_policy=NamePolicy(s["name_policy"]),
        criteria_format=CriteriaFormat(s["criteria_format"]),
        include_abstain=s["include_abstain"],
        allow_duplicate_names=s.get("allow_duplicate_names", False),
    )


def rebuild_selection_input(record: dict[str, Any]) -> dict[str, Any]:
    """The selection-stage request the record's pipeline would send, rebuilt from the record."""
    task = task_from_record(record)
    config = serialization_from_record(record)
    cset = present_task(task, config, order_seed=record["order_seed"], id_seed=record["id_seed"])
    if record["native_single_call"]:
        request = ChatRequest(NATIVE_SYSTEM_PROMPT, render_state(task.state), build_native_tools(cset), "auto", False)
    else:
        request = build_selector_request(task.state, cset, config)
    return thaw(request)


def logged_selection_input(record: dict[str, Any]) -> dict[str, Any]:
    stage = "selection_and_arguments" if record["native_single_call"] else "selection"
    return record["model_inputs"][stage]["request"]
