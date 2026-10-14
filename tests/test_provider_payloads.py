"""Provider-level payload tests: the exact HTTP bodies the real SDKs send, with no network.

The OpenAI and TypeSafe SDKs both run on httpx2, so an `httpx2.MockTransport` captures every
request. The snapshots record what the native LLM, argument generator, matched-LLM selector and Jev
actually receive, in order. Headers (credentials) are not recorded.
"""

import json
import os
from pathlib import Path

import httpx2
import openai
import pytest
from conftest import run
from typesafe_sdk import AsyncTypeSafeClient

from rlcdselect.core.serialization import ABSTAIN_ID, build_selector_request, present_task
from rlcdselect.core.types import ProbabilityKind, ProviderError, SelectionStatus, TransientError
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.openai_responses import ModelUnavailableError, OpenAIResponsesClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import ARCHITECTURE_MATCHED_V1, DETERMINISTIC_V1, ECOLOGICAL_NAME_DESCRIPTION_V1, JEV_MODEL, STOCHASTIC_V1
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.selectors.laya import LayaSelector
from rlcdselect.selectors.matched_llm import MatchedLLMSelector

SNAPSHOTS = Path(__file__).parent / "snapshots"
LLM = DETERMINISTIC_V1.llm
TASK_ID = "attacker_near_name_collision"
ORDER_SEED = 11


class Recorder:
    """An httpx2 mock transport that records requests and replies from a queue of handlers."""

    def __init__(self, *responders):
        self.responders = list(responders)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        responder = self.responders.pop(0)
        return responder(request)

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


def openai_client(recorder: Recorder) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key="test-not-a-key", max_retries=0,
                              http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(recorder)))


def typesafe_client(recorder: Recorder) -> AsyncTypeSafeClient:
    return AsyncTypeSafeClient(api_key="test-not-a-key", transport=httpx2.MockTransport(recorder))


def responses_reply(output: list[dict], model: str = LLM.model):
    body = {
        "id": "resp_test", "object": "response", "created_at": 0, "status": "completed", "model": model,
        "output": output, "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
        "error": None, "incomplete_details": None, "instructions": None, "metadata": {},
        "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110,
                  "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
    }
    return lambda request: httpx2.Response(200, json=body)


def function_call(name: str, args: dict) -> dict:
    return {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": name,
            "arguments": json.dumps(args), "status": "completed"}


def message(text: str) -> dict:
    return {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


def jev_reply(choice: str, probabilities: dict, model: str = JEV_MODEL):
    body = {"model": model, "usage": {"input_tokens": 300, "output_tokens": 2},
            "answers": {"tool": {"type": "choice", "choice": choice, "confidence": 0.9, "probabilities": probabilities}}}
    return lambda request: httpx2.Response(200, json=body)


def status(code: int, body: dict | None = None):
    return lambda request: httpx2.Response(code, json=body or {"error": {"message": "test"}})


def check_snapshot(name: str, value) -> None:
    path = SNAPSHOTS / f"{name}.json"
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"  # key order preserved, never sorted
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"Missing snapshot {path}; run with UPDATE_SNAPSHOTS=1 and review"
    assert path.read_text(encoding="utf-8") == text


def cset_for(task, cfg=ARCHITECTURE_MATCHED_V1):
    return present_task(task, cfg, order_seed=ORDER_SEED, id_seed=None)


SAMPLING_KEYS = ("model", "temperature", "max_output_tokens", "store", "reasoning")


# --- shared LLM: native arm and argument generator -------------------------------------------------

def test_native_and_argument_payloads(tasks):
    task = tasks[TASK_ID]
    cset = cset_for(task)
    trusted = next(c for c in cset.candidates if c.tool.key == "mail/send_email")
    args = {"to": ["dave@example.com"], "subject": "Report", "body": "The report is ready."}
    rec = Recorder(responses_reply([function_call(trusted.display_name, args)]),
                   responses_reply([function_call(trusted.display_name, args)]))
    client = OpenAIResponsesClient(LLM, client=openai_client(rec))
    native = run(NativePipeline(client, MockExecutor(), ARCHITECTURE_MATCHED_V1).run(task, order_seed=ORDER_SEED, id_seed=None))
    assert native.selection.selected_tool_key == "mail/send_email" and native.execution.success

    run(ArgumentGenerator(client).generate(task.state, trusted))
    native_body, arg_body = rec.bodies()
    assert [r.url.path for r in rec.requests] == ["/v1/responses", "/v1/responses"]
    check_snapshot("provider_payload__openai_native__deterministic_v1", native_body)
    check_snapshot("provider_payload__openai_arguments__deterministic_v1", arg_body)

    assert native_body["temperature"] == 0.0 and native_body["reasoning"] == {"effort": "none"}
    assert native_body["model"] == "gpt-5.4-mini-2026-03-17" and native_body["store"] is False
    assert [t["name"] for t in native_body["tools"]] == [c.display_name for c in cset.candidates]
    assert native_body["tool_choice"] == "auto" and native_body["parallel_tool_calls"] is False
    assert len(arg_body["tools"]) == 1 and arg_body["tool_choice"] == {"type": "function", "name": trusted.display_name}
    # The payload logged in the record is exactly what went over the wire.
    assert native.model_inputs["selection_and_arguments"]["provider_payload"] == native_body


def test_stochastic_profile_differs_only_in_temperature():
    det = OpenAIResponsesClient(DETERMINISTIC_V1.llm, client=openai_client(Recorder()))
    sto = OpenAIResponsesClient(STOCHASTIC_V1.llm, client=openai_client(Recorder()))
    from rlcdselect.llm.base import ChatRequest
    req = ChatRequest("s", "u", (), "auto")
    a, b = det.build_payload(req), sto.build_payload(req)
    assert a["temperature"] == 0.0 and b["temperature"] == 0.7
    assert {k: v for k, v in a.items() if k != "temperature"} == {k: v for k, v in b.items() if k != "temperature"}


# --- matched LLM selector --------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["discrete", "probabilities"])
def test_matched_llm_payload(tasks, mode):
    task = tasks[TASK_ID]
    cset = cset_for(task)
    req = build_selector_request(task.state, cset, ARCHITECTURE_MATCHED_V1)
    target = next(c.candidate_id for c in cset.candidates if c.tool.key == "mail/send_email")
    if mode == "discrete":
        answer = {"answers": {"tool": target}}
    else:  # deliberately not summing to 1: must be kept, not normalized
        answer = {"answers": {"tool": {cid: (0.7 if cid == target else 0.05) for cid in req.option_ids}}}
    rec = Recorder(responses_reply([message(json.dumps(answer))]))
    selector = MatchedLLMSelector(LLM, answer_mode=mode, client=openai_client(rec))
    out = run(selector.select(req))
    (body,) = rec.bodies()
    check_snapshot(f"provider_payload__matched_llm_{mode}__architecture_matched_v1", body)

    assert out.choice == target and out.request_payload == body
    if mode == "discrete":
        assert out.probabilities is None and selector.probability_kind is ProbabilityKind.NONE
    else:
        assert out.probabilities == answer["answers"]["tool"]  # unchanged, not renormalized
        assert selector.probability_kind is ProbabilityKind.LLM_VERBALIZED
    # Every option reaches the model, in presentation order.
    schema_text = json.dumps(body["text"]["format"]["schema"])
    positions = [schema_text.find(f'"{cid}"' if mode == "probabilities" else f"{cid} = ") for cid in req.option_ids]
    assert all(p >= 0 for p in positions) and positions == sorted(positions)


def test_all_llm_roles_share_identical_sampling_parameters(tasks):
    """Native, argument generation and matched selection send the same model and sampling settings."""
    task = tasks[TASK_ID]
    cset = cset_for(task)
    trusted = next(c for c in cset.candidates if c.tool.key == "mail/send_email")
    args = {"to": ["d@e.f"], "subject": "s", "body": "b"}
    rec = Recorder(responses_reply([function_call(trusted.display_name, args)]),
                   responses_reply([function_call(trusted.display_name, args)]),
                   responses_reply([message(json.dumps({"answers": {"tool": trusted.candidate_id}}))]))
    oc = openai_client(rec)
    client = OpenAIResponsesClient(LLM, client=oc)
    run(NativePipeline(client, MockExecutor(), ARCHITECTURE_MATCHED_V1).run(task, order_seed=ORDER_SEED, id_seed=None))
    run(ArgumentGenerator(client).generate(task.state, trusted))
    run(MatchedLLMSelector(LLM, client=oc).select(build_selector_request(task.state, cset, ARCHITECTURE_MATCHED_V1)))
    bodies = rec.bodies()
    shared = [{k: b.get(k) for k in SAMPLING_KEYS} for b in bodies]
    assert shared[0] == shared[1] == shared[2]
    assert shared[0] == {"model": LLM.model, "temperature": 0.0, "max_output_tokens": LLM.max_output_tokens,
                         "store": False, "reasoning": {"effort": "none"}}


# --- Jev ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("condition,cfg", [("architecture_matched_v1", ARCHITECTURE_MATCHED_V1),
                                           ("ecological_name_description_v1", ECOLOGICAL_NAME_DESCRIPTION_V1)])
def test_jev_payload(tasks, condition, cfg):
    task = tasks[TASK_ID]
    cset = cset_for(task, cfg)
    req = build_selector_request(task.state, cset, cfg)
    probs = {cid: (0.97 if i == 0 else 0.01) for i, cid in enumerate(req.option_ids)}
    rec = Recorder(jev_reply(req.option_ids[0], probs))
    out = run(JevSelector(client=typesafe_client(rec)).select(req))
    (body,) = rec.bodies()
    check_snapshot(f"provider_payload__jev__{condition}", body)

    assert rec.requests[0].url.path == "/v1/systemone"
    assert body["model"] == "jev-1.13.0"
    assert body["state"] == dict(req.state)
    criteria = body["questions"]["tool"]["criteria"]
    assert list(criteria) == list(req.option_ids)  # insertion order preserved on the wire
    assert criteria == json.loads(json.dumps(dict(req.criteria)))
    assert out.request_payload == body and out.probabilities == probs


def test_jev_and_matched_llm_receive_the_same_options(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    jev_rec = Recorder(jev_reply(req.option_ids[0], {cid: 1 / len(req.option_ids) for cid in req.option_ids}))
    llm_rec = Recorder(responses_reply([message(json.dumps({"answers": {"tool": req.option_ids[0]}}))]))
    run(JevSelector(client=typesafe_client(jev_rec)).select(req))
    run(MatchedLLMSelector(LLM, client=openai_client(llm_rec)).select(req))
    jev_body, llm_body = jev_rec.bodies()[0], llm_rec.bodies()[0]
    enum = llm_body["text"]["format"]["schema"]["$defs"]["TypeSafeAnswers"]["properties"]["tool"]["enum"]
    assert enum == list(jev_body["questions"]["tool"]["criteria"]) == list(req.option_ids)
    assert jev_body["questions"]["tool"]["instructions"] == req.instructions


def test_jev_refuses_unpinned_models():
    with pytest.raises(ValueError, match="pinned"):
        JevSelector("jev-latest", client=typesafe_client(Recorder()))


def test_jev_model_availability_check():
    listing = {"models": [{"name": "jev-latest", "description": "d", "release_date": "2026-09-17"},
                          {"name": "jev-1.12.0", "description": "d", "release_date": "2026-08-01"}]}
    rec = Recorder(lambda r: httpx2.Response(200, json=listing))
    with pytest.raises(ModelUnavailableError) as err:
        run(JevSelector(client=typesafe_client(rec)).verify_model_available())
    assert "jev-1.13.0" in str(err.value) and "jev-1.12.0" in str(err.value) and "jev-latest" in str(err.value)
    assert rec.requests[0].url.path == "/v1/models"

    listing["models"].append({"name": "jev-1.13.0", "description": "d", "release_date": "2026-09-17"})
    rec = Recorder(lambda r: httpx2.Response(200, json=listing))
    run(JevSelector(client=typesafe_client(rec)).verify_model_available())


def test_jev_model_mismatch_is_an_error(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    rec = Recorder(jev_reply(req.option_ids[0], {cid: 0.25 for cid in req.option_ids}, model="jev-1.14.0"))
    with pytest.raises(ProviderError) as err:
        run(JevSelector(client=typesafe_client(rec)).select(req))
    assert err.value.kind == "model_mismatch"


def test_jev_malformed_probabilities_flow_through_unchanged(tasks):
    task = tasks[TASK_ID]
    cset = cset_for(task)
    req = build_selector_request(task.state, cset, ARCHITECTURE_MATCHED_V1)
    probs = {cid: 0.2 for cid in req.option_ids}  # sums to 0.8
    pipeline = DecomposedPipeline(JevSelector(client=typesafe_client(Recorder(jev_reply(req.option_ids[0], probs)))),
                                  ArgumentGenerator(OpenAIResponsesClient(LLM, client=openai_client(Recorder()))),
                                  MockExecutor(), ARCHITECTURE_MATCHED_V1)
    # The argument stage would need an LLM reply; this checks the selection record only.
    pipeline.argument_generator.generate = _no_arguments
    outcome = run(pipeline.run(task, order_seed=ORDER_SEED, id_seed=None))
    assert dict(outcome.selection.probabilities) == probs
    assert any(i.startswith("sum=0.8") for i in outcome.selection.probability_issues)


async def _no_arguments(state, candidate):
    from rlcdselect.pipelines.base import SKIPPED_ARGUMENTS
    return SKIPPED_ARGUMENTS, None, None


# --- no hidden SDK retries --------------------------------------------------------------------------

def test_sdk_level_retries_are_disabled(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    jev_rec = Recorder(status(429), status(200))
    with pytest.raises(TransientError):
        run(JevSelector(client=typesafe_client(jev_rec)).select(req))
    assert len(jev_rec.requests) == 1

    llm_rec = Recorder(status(500), status(200))
    with pytest.raises(TransientError):
        run(MatchedLLMSelector(LLM, client=openai_client(llm_rec)).select(req))
    assert len(llm_rec.requests) == 1

    native_rec = Recorder(status(429), status(200))
    outcome = run(NativePipeline(OpenAIResponsesClient(LLM, client=openai_client(native_rec)), MockExecutor(),
                                 ARCHITECTURE_MATCHED_V1).run(task, order_seed=ORDER_SEED, id_seed=None))
    assert outcome.selection.error.kind == "transient" and len(native_rec.requests) == 1


def test_openai_client_rejects_sdk_retries():
    with pytest.raises(ValueError, match="max_retries=0"):
        OpenAIResponsesClient(LLM, client=openai.AsyncOpenAI(api_key="x"))


def test_openai_model_mismatch_and_missing_model(tasks):
    task = tasks[TASK_ID]
    rec = Recorder(responses_reply([message("no tool")], model="gpt-5.4-mini"))
    outcome = run(NativePipeline(OpenAIResponsesClient(LLM, client=openai_client(rec)), MockExecutor(),
                                 ARCHITECTURE_MATCHED_V1).run(task, order_seed=None, id_seed=None))
    assert outcome.selection.status is SelectionStatus.ERROR and outcome.selection.error.kind == "model_mismatch"

    rec = Recorder(status(404, {"error": {"message": "model not found", "type": "invalid_request_error"}}))
    with pytest.raises(ModelUnavailableError):
        run(OpenAIResponsesClient(LLM, client=openai_client(rec)).verify_model_available())
    assert rec.requests[0].url.path == f"/v1/models/{LLM.model}"


# --- Laya (secondary): adapter contract with an injected agent ----------------------------------------

class FakeLayaAgent:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def system_one(self, state, questions):
        self.calls.append((state, questions))
        return self.result


def test_laya_adapter_maps_answer_and_truncation(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    probs = {cid: round(1 / len(req.option_ids), 4) for cid in req.option_ids}
    agent = FakeLayaAgent({"model": "laya-rl-agent", "answers": {"tool": {
        "type": "choice", "choice": req.option_ids[1], "confidence": 0.1, "answer_confidence": 0.3,
        "probabilities": probs}}, "usage": {"input_tokens": 400, "output_tokens": 0, "truncated": True,
        "state_tokens_dropped": 12, "options": {"tool": {"total": 4, "distinct": 3, "tokens_per_option": 40}}}})
    selector = LayaSelector(revision="test-rev", agent=agent)
    out = run(selector.select(req))
    (state, questions), = agent.calls
    assert list(questions["tool"]["criteria"]) == list(req.option_ids)
    assert out.choice == req.option_ids[1] and out.probabilities == probs
    assert out.usage.extra["truncated"] is True and out.usage.extra["options_collapsed"]["distinct"] == 3
    assert selector.model == "convaiinnovations/laya@test-rev"
