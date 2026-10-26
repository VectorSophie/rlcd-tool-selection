"""External dataset adapters (When2Call, MetaTool, BFCL) on small synthetic rows.

The rows below are written for these tests in each source's *format*; no dataset content is
copied, and nothing is downloaded.
"""

import json

import pytest
from conftest import run
from helpers import call, response

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import present_task
from rlcdselect.core.types import ABSTAIN, ToolRole
from rlcdselect.datasets.external import bfcl, metatool, when2call
from rlcdselect.eval.argmatch import canonical_call, option_leaves, options_mismatches
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.runner import ExperimentConfig, InvariantError, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import ScriptedChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import ARCHITECTURE_MATCHED_V1
from rlcdselect.selectors.mock import ScriptedSelector, output

# --- synthetic When2Call rows ----------------------------------------------------------------------

LAMP = {"name": "home.set_lamp", "description": "Turn a smart lamp on or off.",
        "parameters": {"type": "dict", "required": ["room", "on"],
                       "properties": {"room": {"type": "string"}, "on": {"type": "boolean"},
                                      "level": {"type": "float", "description": "Brightness 0-1."}}}}
THERMO = {"name": "home.set_thermostat", "description": "Set the thermostat.",
          "parameters": {"type": "dict", "required": ["celsius"], "properties": {"celsius": {"type": "integer"}}}}


def w2c(uuid, label, tools, target=None, **extra):
    return {"uuid": uuid, "source": "synthetic", "source_id": "group-1", "question": "Switch on the kitchen lamp.",
            "correct_answer": label, "tools": [json.dumps(t) for t in tools],
            "target_tool": json.dumps(target) if target else None,
            "answers": {"direct": "x", "tool_call": json.dumps({"name": "home.set_lamp",
                                                                 "arguments": {"room": "kitchen", "on": True}}),
                        "request_for_info": "Which room?", "cannot_answer": "I can't."}, **extra}


W2C_ROWS = [
    w2c("u-call", "tool_call", [THERMO, LAMP], LAMP),
    w2c("u-rfi", "request_for_info", [THERMO, LAMP], LAMP, held_out_param="room", orig_question="..."),
    w2c("u-cannot", "cannot_answer", [THERMO]),
    w2c("u-empty", "cannot_answer", []),
    w2c("u-dup", "tool_call", [LAMP, LAMP], LAMP),
    w2c("u-weird", "direct", [LAMP], LAMP),
]

# --- synthetic MetaTool rows -----------------------------------------------------------------------


def mt_prompt(tools):
    lines = "\n".join(f"{i + 1}. tool name: {n}, tool description: {d}" for i, (n, d) in enumerate(tools))
    return ("Choose a tool.\n[List of Tools with Names and Descriptions Start]\n" + lines +
            "\n[List of Tools with Names and Descriptions End]\nExamples...")


MT_TOOLS = [("RecipeFinder", "['Find recipes by ingredient.']"), ("Wine Pairing", "Suggest a wine for a dish."),
            ("TripPlanner", "['Plan a trip.']")]
MT_SUB1 = [{"query": "What can I cook with leeks?", "tool": "RecipeFinder", "index": 7,
            "action_prompt": mt_prompt(MT_TOOLS), "thought_prompt": "..."}]
MT_SUB3 = [{"query": "What is the tallest mountain on Mars?", "tool": "SpaceFacts", "index": 2,
            "action_prompt": mt_prompt(MT_TOOLS), "thought_prompt": "..."}]

# --- synthetic BFCL rows -----------------------------------------------------------------------

AREA = {"name": "geometry.rect_area", "description": "Area of a rectangle.",
        "parameters": {"type": "dict", "required": ["width", "height"],
                       "properties": {"width": {"type": "float"}, "height": {"type": "float"},
                                      "unit": {"type": "string", "description": "Defaults to 'm'."},
                                      "scale": {"type": "integer", "description": "Drawing scale, default 1."},
                                      "filters": {"type": "dict", "properties": {"rounding": {"type": "integer"}}}}}}
CIRCLE = {"name": "geometry_circle", "description": "Area of a circle.",
          "parameters": {"type": "dict", "required": ["r"], "properties": {"r": {"type": "float"}}}}


def q(text, system=None):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": text}]
    return [msgs]


BFCL_ROWS = [
    {"id": "multiple_0", "question": q("Area of a 3 by 4.5 rectangle, rounded to 2 places?"), "function": [CIRCLE, AREA]},
    {"id": "multiple_1", "question": q("Area of a circle with radius 2.", system="Be brief."), "function": [CIRCLE, AREA]},
    {"id": "multiple_2", "question": [[{"role": "user", "content": "a"}], [{"role": "user", "content": "b"}]],
     "function": [CIRCLE]},
    {"id": "multiple_3", "question": q("Two areas, please."), "function": [CIRCLE, AREA]},
]
BFCL_ANSWERS = [
    {"id": "multiple_0", "ground_truth": [{"geometry.rect_area": {"width": [3.0, 3], "height": [4.5],
                                                                  "unit": ["m", ""], "scale": [1, ""],
                                                                  "filters": [{"rounding": [2]}]}}]},
    {"id": "multiple_1", "ground_truth": [{"geometry_circle": {"r": [2.0]}}]},
    {"id": "multiple_2", "ground_truth": [{"geometry_circle": {"r": [1.0]}}]},
    {"id": "multiple_3", "ground_truth": [{"geometry_circle": {"r": [1.0]}}, {"geometry_circle": {"r": [2.0]}}]},
]
BFCL_IRRELEVANT = [{"id": "irrelevance_0", "question": q("Tell me a joke."), "function": [CIRCLE]}]


@pytest.fixture
def adapted():
    return {
        "w2c": when2call.adapt(W2C_ROWS),
        "mt1": metatool.adapt(MT_SUB1, "Task2-Subtask1"),
        "mt3": metatool.adapt(MT_SUB3, "Task2-Subtask3"),
        "bfcl": bfcl.adapt(BFCL_ROWS, "multiple", BFCL_ANSWERS),
        "irr": bfcl.adapt(BFCL_IRRELEVANT, "irrelevance"),
    }


def all_tasks(adapted):
    return [t for r in adapted.values() for t in r.tasks]


# 1
def test_every_included_task_has_a_valid_expected_outcome(adapted):
    for t in all_tasks(adapted):
        keys = {tool.key for tool in t.tools}
        assert t.expected.tool_keys <= keys
        assert t.expected.tool_keys or t.expected.abstain_reason
        assert set(t.roles) == keys


# 2
def test_evaluator_metadata_never_reaches_model_inputs(adapted, tmp_path):
    t = next(t for t in adapted["bfcl"].tasks if t.task_id == "bfcl:multiple_0")
    cset = present_task(t, ARCHITECTURE_MATCHED_V1, order_seed=1, id_seed=None)
    area = next(c for c in cset.candidates if c.tool.name == "geometry_rect_area")
    reply = response(call(area.display_name, {"width": 3, "height": 4.5}))
    native_llm, arg_llm = ScriptedChatClient([reply]), ScriptedChatClient([reply])
    selector = ScriptedSelector([output(area.candidate_id)])
    pipes = [NativePipeline(native_llm, MockExecutor(), ARCHITECTURE_MATCHED_V1),
             DecomposedPipeline(selector, ArgumentGenerator(arg_llm), MockExecutor(), ARCHITECTURE_MATCHED_V1)]
    records = run(run_experiment([t], pipes, ExperimentConfig("a", order_seeds=(1,)), JsonlWriter(tmp_path / "r.jsonl", secrets=())))
    model_side = json.dumps([repr(x) for x in native_llm.requests + arg_llm.requests + selector.requests]
                            + [r["model_inputs"] for r in records])
    for secret in ("bfcl_v1", "multiple_0", "possible_answer", "ShishirPatil", "geometry.rect_area", "tool_name_map"):
        assert secret not in model_side, secret
    assert set(t.state) == {"user_request"}  # only the question is model-visible
    for r in adapted["w2c"].tasks:
        assert set(r.state) == {"user_request"}
        assert r.provenance["source_label"] not in json.dumps(thaw(r.state))
    assert records[0]["task_provenance"]["source_item_id"] == "multiple_0"  # evaluator side keeps it


# 3, 10
def test_source_and_presented_order_are_recorded_and_seeded_order_is_deterministic(adapted, tmp_path):
    (t,) = adapted["mt1"].tasks
    assert t.provenance["source_gold_position"] == 0
    orders = {seed: present_task(t, ARCHITECTURE_MATCHED_V1, order_seed=seed, id_seed=None).tool_order
              for seed in (1, 2, 3)}
    assert orders == {seed: present_task(t, ARCHITECTURE_MATCHED_V1, order_seed=seed, id_seed=None).tool_order
                      for seed in (1, 2, 3)}
    assert any(o != tuple(x.key for x in t.tools) for o in orders.values())
    gold = next(iter(t.expected.tool_keys))
    selector = ScriptedSelector([output("none"), output("none")])
    pipe = DecomposedPipeline(selector, ArgumentGenerator(ScriptedChatClient([])), MockExecutor(), ARCHITECTURE_MATCHED_V1)
    path = tmp_path / "r.jsonl"
    run(run_experiment([t], [pipe], ExperimentConfig("o", order_seeds=(None, 3)), JsonlWriter(path, secrets=())))
    for rec in read_jsonl(path):
        assert rec["source_tool_order"] == [x.key for x in t.tools]
        assert rec["expected_source_positions"] == [0]
        assert rec["expected_presented_positions"] == [rec["tool_order"].index(gold)]
    with pytest.raises(InvariantError, match="source-order bias"):
        run(run_experiment([t], [pipe], ExperimentConfig("o", order_seeds=(None,))))


# 4
def test_duplicate_names_follow_current_policy(adapted):
    reasons = {e.source_item_id: e.reason for e in adapted["w2c"].exclusions}
    assert reasons["u-dup"] == "duplicate_tool_names"  # duplicate visible names are an error, never merged
    from rlcdselect.datasets.external.common import Skip, sanitize_names
    with pytest.raises(Skip, match="name_collision_after_sanitization"):
        sanitize_names(["a.b", "a_b"], set())
    names = {t.task_id: [x.name for x in t.tools] for t in adapted["w2c"].tasks}
    assert names["when2call:u-call"] == ["home_set_thermostat", "home_set_lamp"]
    call_task = next(t for t in adapted["w2c"].tasks if t.task_id == "when2call:u-call")
    assert call_task.provenance["tool_name_map"] == {"home.set_thermostat": "home_set_thermostat",
                                                     "home.set_lamp": "home_set_lamp"}
    assert "tool_name_sanitized" in call_task.provenance["transformations"]


# 5
def test_abstention_labels_map_correctly_and_are_preserved(adapted):
    by_id = {t.task_id: t for t in adapted["w2c"].tasks}
    call_t, rfi, cannot = by_id["when2call:u-call"], by_id["when2call:u-rfi"], by_id["when2call:u-cannot"]
    assert call_t.expected.tool_keys == {"when2call/home_set_lamp"}
    assert rfi.expected.expects_abstention and rfi.expected.abstain_reason == "missing_information"
    assert cannot.expected.expects_abstention and cannot.expected.abstain_reason == "no_suitable_tool"
    assert [t.provenance["source_label"] for t in (call_t, rfi, cannot)] == ["tool_call", "request_for_info", "cannot_answer"]
    assert rfi.roles["when2call/home_set_lamp"] is ToolRole.TRUSTED  # the right tool, information missing
    assert rfi.provenance["held_out_param"] == "room"
    (mt3,) = adapted["mt3"].tasks
    assert mt3.expected.abstain_reason == "no_suitable_tool" and mt3.provenance["source_gold_tool"] == "SpaceFacts"
    (irr,) = adapted["irr"].tasks
    assert irr.expected.expects_abstention and irr.provenance["source_label"] == "irrelevance"


# 6
def test_argument_gold_values_survive_conversion(adapted):
    t = next(t for t in adapted["bfcl"].tasks if t.task_id == "bfcl:multiple_0")
    assert thaw(t.expected.argument_options) == BFCL_ANSWERS[0]["ground_truth"][0]["geometry.rect_area"]
    opts = thaw(t.expected.argument_options)
    assert options_mismatches({"width": 3, "height": 4.5, "filters": {"rounding": 2}}, opts) == []
    assert options_mismatches({"width": 3, "height": 4.5, "unit": "M", "filters": {"rounding": 2}}, opts) == []
    assert options_mismatches({"width": 3, "height": 4.5}, opts) == ["filters: missing"]
    assert options_mismatches({"width": 3, "height": 5, "filters": {"rounding": 2}, "x": 1}, opts) == \
        ["height: 5 not in accepted values", "x: unexpected_parameter"]
    assert canonical_call(opts) == {"width": 3.0, "height": 4.5, "unit": "m", "scale": 1, "filters": {"rounding": 2}}
    ref = next(t for t in adapted["w2c"].tasks if t.task_id == "when2call:u-call").provenance["reference_arguments"]
    assert ref == {"room": "kitchen", "on": True}  # kept as a reference, not scored as gold


# 7
def test_grounding_rules_only_use_values_from_the_source(adapted):
    for t in adapted["bfcl"].tasks:
        if not t.argument_grounding:
            continue
        source_values = {(p, json.dumps(v)) for p, v in option_leaves(thaw(t.expected.argument_options))}
        for path, rule in thaw(t.argument_grounding).items():
            assert rule["origin"] == "bfcl_possible_answer"
            for v in rule["fixture_defaults"]:
                assert (path, json.dumps(v)) in source_values
    t0 = next(t for t in adapted["bfcl"].tasks if t.task_id == "bfcl:multiple_0")
    # Only the typed value the request never states becomes a rule; free text ("m") stays `unknown`,
    # and values found in the request (3, 4.5, 2) need no rule.
    assert thaw(t0.argument_grounding) == {"scale": {"fixture_defaults": [1], "origin": "bfcl_possible_answer"}}


# 8
def test_source_ids_are_preserved(adapted):
    assert [t.provenance["source_item_id"] for t in adapted["w2c"].tasks] == ["u-call", "u-rfi", "u-cannot"]
    assert all(t.task_id.endswith(t.provenance["source_item_id"]) for t in all_tasks(adapted))
    assert adapted["mt1"].tasks[0].provenance["source_item_id"] == "Task2-Subtask1:0"
    assert adapted["mt1"].tasks[0].provenance["source_index_field"] == 7
    for t in all_tasks(adapted):
        p = t.provenance
        for key in ("source_dataset", "source_split", "source_item_id", "source_version_or_commit",
                    "adapter_version", "transformations"):
            assert p[key] is not None or key == "transformations", key


# 9
def test_exclusions_are_reproducible_and_summarized(adapted):
    again = when2call.adapt(W2C_ROWS)
    assert again.exclusions == adapted["w2c"].exclusions
    assert [(e.source_item_id, e.reason) for e in adapted["w2c"].exclusions] == [
        ("u-empty", "no_candidate_tools"), ("u-dup", "duplicate_tool_names"), ("u-weird", "unknown_source_label")]
    s = adapted["w2c"].summary()
    assert (s["source_rows"], s["included"], s["excluded"]) == (6, 3, 3)
    assert s["exclusion_reasons"] == {"no_candidate_tools": 1, "duplicate_tool_names": 1, "unknown_source_label": 1}
    b = {e.source_item_id: e.reason for e in adapted["bfcl"].exclusions}
    assert b == {"multiple_2": "multi_turn", "multiple_3": "multiple_calls_in_ground_truth"}


def test_bfcl_schema_and_state_transformations_are_logged(adapted):
    t = next(t for t in adapted["bfcl"].tasks if t.task_id == "bfcl:multiple_0")
    area = t.tool("bfcl/geometry_rect_area")
    assert area.input_schema["type"] == "object" and area.input_schema["properties"]["width"]["type"] == "number"
    assert {"schema_type_dict_to_object", "schema_type_float_to_number", "tool_name_sanitized"} <= set(t.provenance["transformations"])
    sys_t = next(t for t in adapted["bfcl"].tasks if t.task_id == "bfcl:multiple_1")
    assert thaw(sys_t.state) == {"system_prompt": "Be brief.", "user_request": "Area of a circle with radius 2."}
    assert "system_message_in_state" in sys_t.provenance["transformations"]


def test_metatool_parsing_and_transformations(adapted):
    (t,) = adapted["mt1"].tasks
    assert [x.name for x in t.tools] == ["RecipeFinder", "Wine_Pairing", "TripPlanner"]
    assert [x.description for x in t.tools] == ["Find recipes by ingredient.", "Suggest a wine for a dish.", "Plan a trip."]
    assert list(t.provenance["source_tool_order"]) == ["RecipeFinder", "Wine Pairing", "TripPlanner"]
    assert {"description_list_unwrapped", "empty_input_schema_added", "tool_name_sanitized"} <= set(t.provenance["transformations"])
    assert "requires_order_shuffle" in t.tags


def test_empty_alternatives_and_null_gold_values():
    assert options_mismatches({}, {"a": []}) == [] and options_mismatches({"a": ""}, {"a": []}) == []
    assert options_mismatches({"a": "x"}, {"a": []}) == ["a: 'x' given, but no value is accepted"]
    assert canonical_call({"a": [None], "b": [""]}) == {"a": None}
    assert options_mismatches({"a": None}, {"a": [None]}) == []
