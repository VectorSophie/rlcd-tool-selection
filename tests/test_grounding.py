"""Deterministic argument provenance (grounding) and grounding-aware scoring."""

import json

import pytest
from conftest import run
from helpers import call, response

from rlcdselect.core.placeholders import PlaceholderDetector
from rlcdselect.core.serialization import present_task
from rlcdselect.core.types import ExpectedOutcome, Task, ToolRole, ToolSpec
from rlcdselect.eval.grounding import GroundingChecker, ground_arguments, ground_record
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import ScriptedChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.selectors.mock import ScriptedSelector, output

CALENDAR = {"type": "object", "properties": {
    "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}},
    "required": ["start_date", "end_date"]}
EMAIL = {"type": "object", "properties": {
    "to": {"type": "array", "items": {"type": "string"}}, "subject": {"type": "string"},
    "body": {"type": "string"}, "priority": {"type": "string", "default": "normal"},
    "max_results": {"type": "integer"}}, "required": ["to", "subject"]}


def status(prov, path):
    return prov[path]["status"]


def test_placeholder_is_placeholder():  # 9
    prov = ground_arguments({"to": ["<UNKNOWN>"], "subject": "TBD", "body": "???"}, EMAIL,
                            {"user_request": "Send an email to my landlord."})
    assert [status(prov, p) for p in ("to[0]", "subject", "body")] == ["placeholder"] * 3
    detector = PlaceholderDetector(patterns=[r"XXX"])  # configurable
    assert detector.is_placeholder("XXX") and not detector.is_placeholder("<UNKNOWN>")
    assert not PlaceholderDetector().is_placeholder("TODO")  # a legitimate code-search query


def test_invented_date_range_is_unsupported():  # 10
    prov = ground_arguments({"start_date": "2024-01-01", "end_date": "2024-12-31"}, CALENDAR,
                            {"user_request": "Check my calendar for that day."})
    assert status(prov, "start_date") == status(prov, "end_date") == "unsupported"


def test_explicit_values():  # 11
    state = {"user_request": "Email Jack@Example.com about the 'Q3 budget' and ask for ten copies."}
    prov = ground_arguments({"to": ["jack@example.com"], "subject": "Q3 budget", "max_results": 10}, EMAIL, state)
    assert prov["to[0]"] == {"status": "explicit", "source": "state.user_request", "how": None,
                             "value_type": "email", "required": True}
    assert status(prov, "subject") == "explicit"
    assert prov["max_results"]["status"] == "explicit" and prov["max_results"]["how"] == "number_word"
    long_form = ground_arguments({"start_date": "2026-10-20"}, CALENDAR,
                                 {"user_request": "What is on October 20, 2026?"})
    assert status(long_form, "start_date") == "explicit"  # a normalized date format


def test_schema_default():  # 12
    prov = ground_arguments({"to": ["a@b.co"], "subject": "Hi", "priority": "normal"}, EMAIL,
                            {"user_request": "Email a@b.co, subject Hi."})
    assert prov["priority"]["status"] == "schema_default" and prov["priority"]["source"] == "schema.default"


def test_fixture_declared_default():  # 13
    rules = {"max_results": {"fixture_default": 10}}
    state = {"user_request": "Search the web for the population of Lisbon."}
    assert status(ground_arguments({"max_results": 10}, EMAIL, state, rules), "max_results") == "fixture_default"
    assert status(ground_arguments({"max_results": 5}, EMAIL, state, rules), "max_results") == "unsupported"
    assert status(ground_arguments({"max_results": 10}, EMAIL, state), "max_results") == "unsupported"


def test_deterministic_date_derivations():  # 14
    state = {"user_request": "What's on my calendar tomorrow?", "reference_date": "2026-10-26", "timezone": "Asia/Seoul"}
    prov = ground_arguments({"start_date": "2026-10-27", "end_date": "2026-10-27"}, CALENDAR, state)
    assert prov["start_date"]["status"] == "derived" and prov["start_date"]["how"] == "relative_day"
    stamp = {"type": "object", "properties": {"start": {"type": "string", "format": "date-time"}}}
    ok = ground_arguments({"start": "2026-10-27T00:00:00+09:00"}, stamp, state)
    assert ok["start"]["status"] == "derived" and ok["start"]["how"] == "relative_day+date_to_day_start"
    wrong_tz = ground_arguments({"start": "2026-10-27T00:00:00+02:00"}, stamp, state)
    assert wrong_tz["start"]["status"] == "unsupported"
    weekday = ground_arguments({"start_date": "2026-11-02"}, CALENDAR,  # 2026-10-26 is a Monday
                               {"user_request": "Check next Monday.", "reference_date": "2026-10-26"})
    assert weekday["start_date"]["how"] == "relative_weekday"
    no_reference = ground_arguments({"start_date": "2026-10-27"}, CALENDAR, {"user_request": "What's on tomorrow?"})
    assert status(no_reference, "start_date") == "unsupported"
    restricted = ground_arguments({"start_date": "2026-10-27"}, CALENDAR, state,
                                  {"start_date": {"allowed_derivations": []}})
    assert status(restricted, "start_date") == "unsupported"


def test_ambiguous_values_are_unknown_not_unsupported():  # 15
    state = {"user_request": "Draft an email to bob@example.com saying the numbers are attached.",
             "reference_date": "2026-10-26"}
    prov = ground_arguments({"to": ["bob@example.com"], "subject": "Update",
                             "body": "Hi Bob,\n\nPlease find the numbers attached.\n\nBest regards", "urgent": True},
                            EMAIL, state)
    assert status(prov, "body") == "unknown"  # composed free text
    assert status(prov, "subject") == "unknown"  # a word that is not in the request
    assert status(prov, "urgent") == "unknown"  # booleans cannot be traced
    stamp = {"type": "object", "properties": {"start": {"type": "string", "format": "date-time"}}}
    tod = ground_arguments({"start": "2026-10-26T20:00:00"}, stamp,
                           {"user_request": "Book something today at 8pm.", "reference_date": "2026-10-26"})
    assert tod["start"]["status"] == "unknown" and tod["start"]["how"] == "time_of_day_not_traced"


def test_nested_paths_and_declared_sources():  # 17
    schema = {"type": "object", "properties": {
        "attendees": {"type": "array", "items": {"type": "object", "properties": {"email": {"type": "string"}},
                                                 "required": ["email"]}},
        "start": {"type": "object", "properties": {"date": {"type": "string", "format": "date"}}}},
        "required": ["attendees"]}
    state = {"user_request": "Invite my landlord on 2026-11-03.", "contacts": {"landlord": "ll@example.com"},
             "note": "cc spare@example.com"}
    args = {"attendees": [{"email": "ll@example.com"}, {"email": "spare@example.com"}], "start": {"date": "2026-11-03"}}
    prov = ground_arguments(args, schema, state)
    assert list(prov) == ["attendees[0].email", "attendees[1].email", "start.date"]
    assert prov["attendees[0].email"]["source"] == "state.contacts.landlord"
    assert prov["attendees[0].email"]["required"] is True and prov["start.date"]["required"] is False
    rules = {"attendees[*].email": {"sources": ["state.contacts"]}}
    restricted = ground_arguments(args, schema, state, rules)
    assert status(restricted, "attendees[0].email") == "explicit"
    assert status(restricted, "attendees[1].email") == "unsupported"  # present, but not in the declared source


SENTINEL = "EVALUATOR-ONLY-7f3a"


def grounded_task(fixtures):
    _, tasks = fixtures
    base = next(t for t in tasks if t.task_id == "missing_info_calendar")
    rules = {"start_date": {"sources": [f"state.{SENTINEL}"], "fixture_default": SENTINEL}}
    return Task(base.task_id, base.state, base.tools, base.expected, base.roles, base.tags, argument_grounding=rules)


def test_evaluator_metadata_never_reaches_any_model(fixtures, serialization, tmp_path):  # 16
    task = grounded_task(fixtures)
    cset = present_task(task, serialization, order_seed=None, id_seed=None)
    cal = next(c for c in cset.candidates if c.tool.key == "calendar/calendar_lookup")
    reply = response(call(cal.display_name, {"start_date": "2024-01-01", "end_date": "2024-12-31"}))
    native_llm, arg_llm = ScriptedChatClient([reply]), ScriptedChatClient([reply])
    selector = ScriptedSelector([output(cal.candidate_id)])
    pipelines = [NativePipeline(native_llm, MockExecutor(), serialization),
                 DecomposedPipeline(selector, ArgumentGenerator(arg_llm), MockExecutor(), serialization)]
    path = tmp_path / "r.jsonl"
    records = run(run_experiment([task], pipelines, ExperimentConfig("g"), JsonlWriter(path, secrets=())))
    seen_by_models = json.dumps([repr(r) for r in native_llm.requests + arg_llm.requests + selector.requests]
                                + [r["model_inputs"] for r in records])
    assert SENTINEL not in seen_by_models
    assert all(SENTINEL in json.dumps(r["expected"]["argument_grounding"]) for r in read_jsonl(path))  # evaluator side


def test_logged_arguments_unchanged_and_scoring_kept_separate(fixtures, serialization, tmp_path):  # 18, 19
    _, tasks = fixtures
    task = next(t for t in tasks if t.task_id == "obvious_search_web")
    cset = present_task(task, serialization, order_seed=None, id_seed=None)
    web = next(c for c in cset.candidates if c.tool.key == "web/search_web")
    invented = {"query": "current population of Lisbon", "max_results": 7}
    selector = ScriptedSelector([output(web.candidate_id)])
    pipeline = DecomposedPipeline(selector, ArgumentGenerator(ScriptedChatClient([response(call(web.display_name, invented))])),
                                  MockExecutor(), serialization)
    path = tmp_path / "r.jsonl"
    run(run_experiment([task], [pipeline], ExperimentConfig("g"), JsonlWriter(path, secrets=())))
    (rec,) = read_jsonl(path)
    assert rec["arguments"] == invented  # never rewritten or hidden
    assert rec["task_success"] is True  # original definition unchanged
    assert rec["argument_grounding_ok"] is False and rec["unsupported_argument_count"] == 1
    assert rec["unsupported_required_argument_count"] == 0  # max_results is optional
    assert rec["grounded_task_success"] is False
    assert rec["argument_provenance"]["max_results"]["status"] == "unsupported"
    assert rec["schema_version"] == 3


def test_old_records_can_be_rescored_without_modification(fixtures):
    record = {"tools_before": [{"key": "calendar/calendar_lookup", "input_schema": CALENDAR}],
              "selected_tool": "calendar/calendar_lookup", "state": {"user_request": "Check my calendar for that day."},
              "arguments": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
              "expected": {"tool_keys": []}, "task_success": False, "abstention_expected": True}
    before = json.dumps(record)
    g = ground_record(record)
    assert json.dumps(record) == before
    assert g["argument_grounding_ok"] is False and g["unsupported_argument_count"] == 2
    assert g["grounded_task_success"] is False


def test_checker_handles_missing_schema_and_odd_values():
    prov = GroundingChecker().check({"x": None, "y": {"z": [1.5]}}, None, {"user_request": "use 1.5"})
    assert status(prov, "x") == "unknown" and status(prov, "y.z[0]") == "explicit"
