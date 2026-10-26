import pytest
from conftest import run
from helpers import call, response

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import ABSTAIN_ID, Representation, SerializationConfig, NamePolicy
from rlcdselect.core.types import (
    ArgumentStatus,
    ProbabilityKind,
    ProviderOutputError,
    RetryPolicy,
    SelectionStatus,
    TransientError,
)
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.base import ForcedTool
from rlcdselect.llm.fake import KeywordChatClient, ScriptedChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.selectors.mock import ScriptedSelector, output

CAL_ARGS = {"start_date": "2026-10-20", "end_date": "2026-10-22"}


def decomposed(selector, llm, serialization, executor=None, retry=RetryPolicy()):
    return DecomposedPipeline(selector, ArgumentGenerator(llm, retry), executor or MockExecutor(), serialization, retry)


def id_of(outcome_or_cset, key):
    cset = getattr(outcome_or_cset, "candidate_set", outcome_or_cset)
    return next(c.candidate_id for c in cset.candidates if c.tool.key == key)


# --- what each model receives -------------------------------------------------------------------

def test_native_receives_all_candidate_tools(tasks, serialization):  # required test 1
    task = tasks["attacker_with_decoy"]
    llm = KeywordChatClient()
    outcome = run(NativePipeline(llm, MockExecutor(), serialization).run(task, order_seed=5, id_seed=None))
    sent = llm.requests[0]
    assert {t.function_name for t in sent.tools} == {c.display_name for c in outcome.candidate_set.candidates}
    assert len(sent.tools) == len(task.tools)
    assert [t.candidate_id for t in sent.tools] == [c.candidate_id for c in outcome.candidate_set.candidates]
    assert sent.tool_choice == "auto" and sent.parallel_tool_calls is False
    for t in sent.tools:  # native always exposes description and schema
        tool = outcome.candidate_set.by_id(t.candidate_id).tool
        assert t.description == tool.description and t.parameters == thaw(tool.input_schema)


def test_decomposed_selector_receives_configured_representation(tasks):  # required test 2
    task = tasks["obvious_calendar"]
    for rep in Representation:
        cfg = SerializationConfig(representation=rep)
        selector = ScriptedSelector([output(ABSTAIN_ID)])
        run(decomposed(selector, KeywordChatClient(), cfg).run(task, order_seed=None, id_seed=None))
        req = selector.requests[0]
        assert req.config == cfg
        texts = [req.criteria[c] for c in req.candidate_ids]
        assert all(("Input schema:" in t) == (rep is Representation.NAME_DESCRIPTION_SCHEMA) for t in texts)
        assert all((":" in t) == (rep is not Representation.NAME_ONLY) for t in texts)


def test_every_decomposed_selector_receives_the_identical_request(tasks, serialization):  # required tests 3, 4
    task = tasks["attacker_with_decoy"]
    # Stand-ins for the matched LLM, Jev and Laya: the pipeline, not the selector, builds the request.
    selectors = [ScriptedSelector([output(ABSTAIN_ID)], selector_id=s) for s in ("matched_llm", "jev", "laya")]
    for s in selectors:
        run(decomposed(s, KeywordChatClient(), serialization).run(task, order_seed=9, id_seed=None))
    first = thaw(selectors[0].requests[0])
    assert all(thaw(s.requests[0]) == first for s in selectors[1:])


def test_roles_are_never_visible_to_models(core, serialization):
    for task in core:
        selector = ScriptedSelector([output(ABSTAIN_ID)])
        llm = KeywordChatClient()
        run(decomposed(selector, llm, serialization).run(task, order_seed=None, id_seed=None))
        run(NativePipeline(llm, MockExecutor(), serialization).run(task, order_seed=None, id_seed=None))
        seen = str(thaw(selector.requests[0])) + str(thaw(llm.requests[-1]))
        for word in ("attacker", "decoy", "trusted", "irrelevant", "role"):
            assert word not in seen


def test_argument_generator_receives_exactly_the_selected_tool(tasks, serialization):  # required test 5
    task = tasks["attacker_with_decoy"]
    llm = KeywordChatClient()
    pipeline = decomposed(ScriptedSelector([lambda req: output(req.candidate_ids[1])]), llm, serialization)
    outcome = run(pipeline.run(task, order_seed=2, id_seed=None))
    assert outcome.selection.status is SelectionStatus.SELECTED
    (arg_request,) = llm.requests
    selected = outcome.candidate_set.by_id(outcome.selection.selected_candidate_id)
    assert len(arg_request.tools) == 1
    assert arg_request.tools[0].candidate_id == selected.candidate_id
    assert arg_request.tool_choice == ForcedTool(selected.display_name)


def test_argument_generator_cannot_change_the_selected_tool(tasks, serialization):  # required test 6
    task = tasks["similar_send_not_draft"]
    executor = MockExecutor()
    llm = ScriptedChatClient([response(call("create_email_draft", {"to": ["a@b.c"], "subject": "s", "body": "b"}))])
    pipeline = decomposed(ScriptedSelector([lambda req: output(id_of(_cset(task, serialization), "mail/send_email"))]),
                          llm, serialization, executor)
    outcome = run(pipeline.run(task, order_seed=None, id_seed=None))
    assert outcome.selection.selected_tool_key == "mail/send_email"
    assert outcome.arguments.status is ArgumentStatus.ERROR
    assert outcome.arguments.error.kind == "tool_mismatch"
    assert outcome.execution is None and executor.calls == []


def _cset(task, cfg):
    from rlcdselect.core.serialization import present_task
    return present_task(task, cfg, order_seed=None, id_seed=None)


# --- abstention and error separation ------------------------------------------------------------

def test_abstention_is_explicit_in_both_arms(tasks, serialization):  # required test 11
    task = tasks["no_tool_translation"]
    native = run(NativePipeline(ScriptedChatClient([response(text="I can answer directly.")]), MockExecutor(),
                                serialization).run(task, order_seed=None, id_seed=None))
    dec = run(decomposed(ScriptedSelector([output(ABSTAIN_ID)]), ScriptedChatClient([]), serialization)
              .run(task, order_seed=None, id_seed=None))
    for outcome in (native, dec):
        assert outcome.selection.status is SelectionStatus.ABSTAINED
        assert outcome.selection.error is None
        assert outcome.arguments.status is ArgumentStatus.SKIPPED
        assert outcome.execution is None


def test_selector_errors_are_distinct_from_wrong_selections(tasks, serialization):  # required test 12
    task = tasks["obvious_calendar"]
    wrong = run(decomposed(ScriptedSelector([output("t0")]), KeywordChatClient(), serialization)
                .run(task, order_seed=None, id_seed=None))
    assert wrong.selection.status is SelectionStatus.SELECTED and wrong.selection.error is None

    invalid = run(decomposed(ScriptedSelector([output("t99")]), KeywordChatClient(), serialization)
                  .run(task, order_seed=None, id_seed=None))
    assert invalid.selection.status is SelectionStatus.ERROR
    assert invalid.selection.error.kind == "invalid_choice"

    crashed = run(decomposed(ScriptedSelector([ProviderOutputError("malformed_output", "bad")]), KeywordChatClient(),
                             serialization).run(task, order_seed=None, id_seed=None))
    assert crashed.selection.status is SelectionStatus.ERROR
    assert crashed.selection.error.kind == "malformed_output" and crashed.selection.error.stage == "selection"

    native_unknown = run(NativePipeline(ScriptedChatClient([response(call("not_a_tool", {}))]), MockExecutor(),
                                        serialization).run(task, order_seed=None, id_seed=None))
    assert native_unknown.selection.error.kind == "invalid_tool_name"

    native_multi = run(NativePipeline(
        ScriptedChatClient([response(call("calendar_lookup", CAL_ARGS), call("search_web", {"query": "x"}))]),
        MockExecutor(), serialization).run(task, order_seed=None, id_seed=None))
    assert native_multi.selection.status is SelectionStatus.MULTIPLE


def test_execution_errors_are_distinct_from_wrong_selections(tasks, serialization):  # required test 13
    task = tasks["obvious_calendar"]

    def boom(args):
        raise RuntimeError("calendar service down")

    executor = MockExecutor({"calendar/calendar_lookup": boom})
    llm = ScriptedChatClient([response(call("calendar_lookup", CAL_ARGS))])
    outcome = run(NativePipeline(llm, executor, serialization).run(task, order_seed=None, id_seed=None))
    assert outcome.selection.status is SelectionStatus.SELECTED and outcome.selection.error is None
    assert outcome.arguments.status is ArgumentStatus.OK
    assert outcome.execution.success is False and outcome.execution.error.kind == "tool_error"

    llm = ScriptedChatClient([response(call("calendar_lookup", {"start_date": "2026-10-20"}))])  # missing end_date
    outcome = run(NativePipeline(llm, MockExecutor(), serialization).run(task, order_seed=None, id_seed=None))
    assert outcome.arguments.schema_valid is False
    assert outcome.execution.error.kind == "invalid_arguments"


def test_unparseable_arguments_are_argument_errors(tasks, serialization):
    task = tasks["obvious_calendar"]
    llm = ScriptedChatClient([response(call("calendar_lookup", None, raw="{not json"))])
    outcome = run(NativePipeline(llm, MockExecutor(), serialization).run(task, order_seed=None, id_seed=None))
    assert outcome.selection.status is SelectionStatus.SELECTED
    assert outcome.arguments.error.kind == "invalid_json" and outcome.execution is None


def test_presentation_failure_is_an_error_not_a_selection(tasks):
    task = tasks["stress_exact_name_collision"]
    cfg = SerializationConfig(name_policy=NamePolicy.TOOL_NAME)
    for outcome in (
        run(NativePipeline(ScriptedChatClient([]), MockExecutor(), cfg).run(task, order_seed=None, id_seed=None)),
        run(decomposed(ScriptedSelector([]), ScriptedChatClient([]), cfg).run(task, order_seed=None, id_seed=None)),
    ):
        assert outcome.selection.status is SelectionStatus.ERROR
        assert outcome.selection.error.stage == "presentation"


# --- probabilities and retries -------------------------------------------------------------------

def test_malformed_probabilities_are_flagged_not_normalized(tasks, serialization):
    task = tasks["obvious_calendar"]
    probs = {"t0": 0.2, "t1": 0.2, "t2": 0.2, ABSTAIN_ID: 0.2}  # sums to 0.8
    selector = ScriptedSelector([output("t2", probs)], probability_kind=ProbabilityKind.RLCD_NATIVE)
    outcome = run(decomposed(selector, KeywordChatClient(), serialization).run(task, order_seed=None, id_seed=None))
    assert dict(outcome.selection.probabilities) == probs
    assert any(i.startswith("sum=") for i in outcome.selection.probability_issues)
    assert outcome.selection.probability_kind is ProbabilityKind.RLCD_NATIVE


def test_retries_are_explicit_and_logged(tasks, serialization):  # required test 17
    task = tasks["obvious_calendar"]
    # Default policy: one attempt, a transient failure is an error.
    outcome = run(decomposed(ScriptedSelector([TransientError("429")]), KeywordChatClient(), serialization)
                  .run(task, order_seed=None, id_seed=None))
    assert outcome.selection.error.kind == "transient" and len(outcome.selection.attempts) == 1

    # With retries enabled, each attempt is recorded.
    selector = ScriptedSelector([TransientError("429"), TransientError("503"), output("t2")])
    outcome = run(decomposed(selector, KeywordChatClient(), serialization, retry=RetryPolicy(max_attempts=3))
                  .run(task, order_seed=None, id_seed=None))
    assert outcome.selection.status is SelectionStatus.SELECTED
    assert [a.error_kind for a in outcome.selection.attempts] == ["transient", "transient", None]
    assert outcome.selection.retry_count == 2

    # Contract violations are never retried, even when retries are allowed.
    selector = ScriptedSelector([ProviderOutputError("malformed_output", "bad"), output("t2")])
    outcome = run(decomposed(selector, KeywordChatClient(), serialization, retry=RetryPolicy(max_attempts=3))
                  .run(task, order_seed=None, id_seed=None))
    assert outcome.selection.status is SelectionStatus.ERROR and len(outcome.selection.attempts) == 1


def test_pipeline_runs_do_not_mutate_fixtures(core, serialization):  # required test 9 (pipeline part)
    from rlcdselect.core.jsonutil import canonical_json
    tasks = core
    before = canonical_json([[t.tools, t.state, t.roles] for t in tasks])
    llm = KeywordChatClient()
    for task in tasks:
        run(NativePipeline(llm, MockExecutor(), serialization).run(task, order_seed=1, id_seed=2))
    assert canonical_json([[t.tools, t.state, t.roles] for t in tasks]) == before


@pytest.mark.parametrize("value", ["<UNKNOWN>", " <recipient email> ", "[RECIPIENT]", "{{subject}}", "unknown", "N/A", "TBD"])
def test_mock_executor_refuses_placeholder_arguments(value):
    """Seen live: for 'Send an email to my landlord.' the argument step filled every field with
    '<UNKNOWN>'. That is schema-valid, but a real tool would act on it, so it is not a success."""
    from rlcdselect.core.types import ToolSpec
    from rlcdselect.execution.mock import MockExecutor

    tool = ToolSpec(server_id="mail", name="send_email", description="Send an email.",
                    input_schema={"type": "object", "properties": {"to": {"type": "array", "items": {"type": "string"}},
                                                                   "body": {"type": "string"}}})
    result = run(MockExecutor().call_tool(tool, {"to": [value], "body": "The report is ready."}))
    assert not result.success and result.error.kind == "placeholder_arguments" and "to/0" in result.error.message
    ok = run(MockExecutor().call_tool(tool, {"to": ["dave@example.com"], "body": "Use <b>bold</b> if unknown."}))
    assert ok.success
