"""The budget guard wired through the real provider clients (HTTP mocked; no network, no spend).

Every arm runs through the same OpenRouter/TypeSafe client code that live runs use, so these tests
check that each billed call's reported `usage.cost` reaches the guard exactly once: native selection
and arguments share one call, decomposed arms bill selection and arguments separately, and calls
that were served but then failed output validation are still charged.
"""

import json

import httpx2
import pytest
from conftest import run
from test_provider_payloads import (
    ARGS,
    LLM,
    TASK_ID,
    Recorder,
    chat_reply,
    cset_for,
    jev_reply,
    or_client,
    tool_call,
    trusted_candidate,
    ts_client,
)

from rlcdselect.core.serialization import build_selector_request
from rlcdselect.core.types import FatalRunError
from rlcdselect.eval.budget import BudgetGuard
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.openrouter import OpenRouterChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import ARCHITECTURE_MATCHED_V1
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.selectors.matched_llm import MatchedLLMSelector

JEV_COST = 0.0000126  # what jev_reply reports


def costing(responder, cost: float, generation_id: str):
    """Rewrite a mocked reply's reported cost and generation id."""

    def respond(request):
        resp = responder(request)
        body = resp.json()
        body["usage"]["cost"], body["id"] = cost, generation_id
        return httpx2.Response(resp.status_code, json=body, headers=dict(resp.headers))

    return respond


def arms(task, or_rec: Recorder, ts_rec: Recorder):
    llm = OpenRouterChatClient(LLM, client=or_client(or_rec))
    arguments = ArgumentGenerator(llm)
    executor = MockExecutor()
    return [
        NativePipeline(llm, executor, ARCHITECTURE_MATCHED_V1),
        DecomposedPipeline(MatchedLLMSelector(LLM, client=llm.sdk_client), arguments, executor, ARCHITECTURE_MATCHED_V1),
        DecomposedPipeline(JevSelector(client=ts_client(ts_rec)), arguments, executor, ARCHITECTURE_MATCHED_V1),
    ]


def happy_path(task):
    trusted = trusted_candidate(task)
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    selected = tool_call(trusted.display_name, ARGS)
    or_rec = Recorder(
        costing(chat_reply(tool_calls=selected), 0.001, "gen-native"),
        costing(chat_reply(content=json.dumps({"answers": {"tool": trusted.candidate_id}}), finish="stop"),
                0.002, "gen-matched-select"),
        costing(chat_reply(tool_calls=selected), 0.003, "gen-matched-args"),
        costing(chat_reply(tool_calls=selected), 0.004, "gen-jev-args"),
    )
    probabilities = {o: (1.0 if o == trusted.candidate_id else 0.0) for o in req.option_ids}
    ts_rec = Recorder(jev_reply(trusted.candidate_id, probabilities))
    return or_rec, ts_rec


def test_each_billed_call_is_charged_exactly_once(tasks, tmp_path):
    task = tasks[TASK_ID]
    or_rec, ts_rec = happy_path(task)
    guard = BudgetGuard(cap_usd=1.0)
    path = tmp_path / "r.jsonl"
    records = run(run_experiment([task], arms(task, or_rec, ts_rec), ExperimentConfig("w", order_seeds=(11,)),
                                 JsonlWriter(path, secrets=()), budget=guard))
    assert [r["selection_status"] for r in records] == ["selected"] * 3
    charged = {r["pipeline"]: r["cost_charged_usd"] for r in records}
    # Native arguments come from the selection call: one call, charged once.
    assert charged == pytest.approx({"native_llm": 0.001, "matched_llm": 0.002 + 0.003, "jev": JEV_COST + 0.004})
    assert len(or_rec.requests) == 4 and len(ts_rec.requests) == 1
    assert guard.spent_usd == pytest.approx(0.01 + JEV_COST)
    assert guard.reported_usd == pytest.approx(guard.spent_usd)
    assert guard.estimated_usd == 0.0  # every call reported its cost
    assert [line["cost_charged_usd"] for line in read_jsonl(path)] == [r["cost_charged_usd"] for r in records]


def test_cap_stops_before_the_next_billed_call(tasks, tmp_path):
    task = tasks[TASK_ID]
    or_rec, ts_rec = happy_path(task)
    guard = BudgetGuard(cap_usd=0.005)  # reached by native (0.001) + matched (0.005)
    path = tmp_path / "r.jsonl"
    with pytest.raises(FatalRunError, match="reached the cap"):
        run(run_experiment([task], arms(task, or_rec, ts_rec), ExperimentConfig("w", order_seeds=(11,)),
                           JsonlWriter(path, secrets=()), budget=guard))
    assert len(or_rec.requests) == 3 and ts_rec.requests == []  # Jev never called
    lines = read_jsonl(path)
    assert [line["record_type"] for line in lines] == ["run", "run", "run_aborted"]
    assert lines[-1]["error_kind"] == "budget_exceeded" and lines[-1]["pipeline"] == "matched_llm"


def test_fatal_abort_charges_the_served_call(tasks, tmp_path):
    task = tasks[TASK_ID]
    rec = Recorder(costing(chat_reply(tool_calls=tool_call("send_email", ARGS), provider="Amazon Bedrock"),
                           0.002, "gen-wrong-provider"))
    guard = BudgetGuard(cap_usd=1.0)
    pipeline = NativePipeline(OpenRouterChatClient(LLM, client=or_client(rec)), MockExecutor(), ARCHITECTURE_MATCHED_V1)
    with pytest.raises(FatalRunError, match="provider"):
        run(run_experiment([task], [pipeline], ExperimentConfig("w"), JsonlWriter(tmp_path / "r.jsonl", secrets=()),
                           budget=guard))
    assert guard.spent_usd == pytest.approx(0.002)
    (abort,) = read_jsonl(tmp_path / "r.jsonl")
    assert abort["budget"]["spent_usd"] == pytest.approx(0.002)


def test_served_calls_that_fail_validation_are_still_charged(tasks):
    """Truncated or refused replies are billed by OpenRouter even though the harness rejects them."""
    task = tasks[TASK_ID]
    trusted = trusted_candidate(task)
    rec = Recorder(
        costing(chat_reply(tool_calls=tool_call("send_email", ARGS), finish="length"), 0.002, "gen-native-trunc"),
        costing(chat_reply(content="not json at all", finish="stop"), 0.003, "gen-matched-bad"),
        costing(chat_reply(tool_calls=tool_call(trusted.display_name, ARGS), finish="length"), 0.004, "gen-args-trunc"),
    )
    llm = OpenRouterChatClient(LLM, client=or_client(rec))
    guard = BudgetGuard(cap_usd=1.0)
    native = NativePipeline(llm, MockExecutor(), ARCHITECTURE_MATCHED_V1)
    matched = DecomposedPipeline(MatchedLLMSelector(LLM, client=llm.sdk_client), ArgumentGenerator(llm),
                                 MockExecutor(), ARCHITECTURE_MATCHED_V1)
    records = run(run_experiment([task], [native, matched], ExperimentConfig("w", order_seeds=(11,)), budget=guard))
    assert [r["selection_status"] for r in records] == ["error", "error"]
    assert [r["cost_charged_usd"] for r in records] == pytest.approx([0.002, 0.003])

    result, _, _ = run(ArgumentGenerator(llm).generate(task.state, trusted))
    assert result.error.kind == "incomplete_response"
    assert result.provider_meta["cost"] == 0.004
    assert guard.charge({"pipeline": "jev", "selector_id": "jev", "argument_provider_meta": result.provider_meta}) == \
        pytest.approx(0.004)
