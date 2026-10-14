"""Provider-level payload tests: the exact HTTP bodies the real SDKs send, with no network.

The OpenAI SDK (pointed at OpenRouter) and the TypeSafe SDK both run on httpx2, so an
`httpx2.MockTransport` captures every request. The snapshots record what the native LLM, argument
generator, matched-LLM selector and Jev actually receive, in order. Headers (credentials) are not
recorded.
"""

import json
import os
from pathlib import Path

import httpx2
import openai
import pytest
from conftest import run
from typesafe_sdk import AsyncTypeSafeClient

from rlcdselect.core.serialization import build_selector_request, present_task
from rlcdselect.core.types import FatalRunError, ProbabilityKind, SelectionStatus, TransientError
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.base import ChatRequest
from rlcdselect.llm.openrouter import (
    SHARED_LLM_REQUIRED_PARAMETERS,
    ModelUnavailableError,
    OpenRouterCatalog,
    OpenRouterChatClient,
)
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import (
    ARCHITECTURE_MATCHED_V1,
    DETERMINISTIC_V1,
    ECOLOGICAL_NAME_DESCRIPTION_V1,
    JEV_MODEL,
    STOCHASTIC_V1,
)
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.selectors.laya import LayaSelector
from rlcdselect.selectors.matched_llm import MatchedLLMSelector
from rlcdselect.startup import verify_live_models

SNAPSHOTS = Path(__file__).parent / "snapshots"
LLM = DETERMINISTIC_V1.llm
TASK_ID = "attacker_near_name_collision"
ORDER_SEED = 11
JEV_BUILD = "typesafe/jev-1.13-20260917"
SHARED_KEYS = ("model", "temperature", "max_tokens", "reasoning", "provider")


class Recorder:
    """An httpx2 mock transport handler: records requests, replies from a queue (or by URL path)."""

    def __init__(self, *responders, routes=None):
        self.responders = list(responders)
        self.routes = routes or {}
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.url.path in self.routes:
            return self.routes[request.url.path](request)
        return self.responders.pop(0)(request)

    def bodies(self, path_suffix: str = "") -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.content and r.url.path.endswith(path_suffix)]


def or_client(rec: Recorder) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key="test-not-a-key", base_url="https://openrouter.ai/api/v1", max_retries=0,
                              http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(rec)))


def ts_client(rec: Recorder) -> AsyncTypeSafeClient:
    return AsyncTypeSafeClient(api_key="test-not-a-key", base_url="https://openrouter.ai/api",
                               transport=httpx2.MockTransport(rec))


def chat_reply(*, tool_calls=None, content=None, model=LLM.model, provider="Anthropic", reasoning_tokens=0,
               finish="tool_calls"):
    body = {
        "id": "gen-test-123", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content, "tool_calls": tool_calls}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110, "cost": 0.00015,
                  "completion_tokens_details": {"reasoning_tokens": reasoning_tokens}},
    }
    if provider is not None:
        body["provider"] = provider
    return lambda request: httpx2.Response(200, json=body, headers={"x-request-id": "req-test-abc"})


def tool_call(name: str, args: dict) -> list[dict]:
    return [{"id": "call_1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]


def jev_reply(choice, probabilities, model=JEV_BUILD, provider="TypeSafe"):
    body = {"id": "gen-dec-test", "model": model, "provider": provider,
            "usage": {"input_tokens": 300, "output_tokens": 2, "cost": 0.0000126},
            "answers": {"tool": {"type": "choice", "choice": choice, "confidence": 0.9, "probabilities": probabilities}}}
    return lambda request: httpx2.Response(200, json=body)


def status(code: int, body: dict | None = None):
    return lambda request: httpx2.Response(code, json=body or {"error": {"message": "test", "code": code}})


def check_snapshot(name: str, value) -> None:
    path = SNAPSHOTS / f"{name}.json"
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"  # key order preserved, never sorted
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"Missing snapshot {path}; run with UPDATE_SNAPSHOTS=1 and review"
    assert path.read_text(encoding="utf-8") == text


def cset_for(task, cfg=ARCHITECTURE_MATCHED_V1):
    return present_task(task, cfg, order_seed=ORDER_SEED, id_seed=None)


def trusted_candidate(task):
    return next(c for c in cset_for(task).candidates if c.tool.key == "mail/send_email")


ARGS = {"to": ["dave@example.com"], "subject": "Report", "body": "The report is ready."}


# --- shared LLM: native arm and argument generator -------------------------------------------------

def test_native_and_argument_payloads(tasks):
    task = tasks[TASK_ID]
    trusted = trusted_candidate(task)
    rec = Recorder(chat_reply(tool_calls=tool_call(trusted.display_name, ARGS)),
                   chat_reply(tool_calls=tool_call(trusted.display_name, ARGS)))
    client = OpenRouterChatClient(LLM, client=or_client(rec))
    native = run(NativePipeline(client, MockExecutor(), ARCHITECTURE_MATCHED_V1).run(task, order_seed=ORDER_SEED, id_seed=None))
    assert native.selection.selected_tool_key == "mail/send_email" and native.execution.success
    arguments, _, _ = run(ArgumentGenerator(client).generate(task.state, trusted))
    native_body, arg_body = rec.bodies()
    assert [r.url.path for r in rec.requests] == ["/api/v1/chat/completions"] * 2
    check_snapshot("provider_payload__openrouter_native__deterministic_v1", native_body)
    check_snapshot("provider_payload__openrouter_arguments__deterministic_v1", arg_body)

    assert native_body["model"] == "anthropic/claude-haiku-4.5"
    assert native_body["temperature"] == 0.0 and native_body["reasoning"] == {"enabled": False}
    assert native_body["provider"] == {"only": ["anthropic"], "allow_fallbacks": False, "require_parameters": True}
    assert "parallel_tool_calls" not in native_body  # unsupported by the Anthropic endpoint
    assert [t["function"]["name"] for t in native_body["tools"]] == [c.display_name for c in cset_for(task).candidates]
    assert native_body["tool_choice"] == "auto"
    assert len(arg_body["tools"]) == 1
    assert arg_body["tool_choice"] == {"type": "function", "function": {"name": trusted.display_name}}

    # Everything the run must log, for both stages.
    for meta in (native.selection.provider_meta, arguments.provider_meta):
        assert meta["requested_model"] == "anthropic/claude-haiku-4.5"
        assert meta["returned_model"] == "anthropic/claude-haiku-4.5"
        assert meta["provider"] == "Anthropic" and meta["provider_source"] == "response"
        assert meta["generation_id"] == "gen-test-123"
        assert meta["response_headers"] == {"x-request-id": "req-test-abc"}
        assert meta["temperature"] == 0.0 and meta["thinking"] == "disabled" and meta["reasoning_tokens"] == 0
    assert native.selection.usage.input_tokens == 100 and native.selection.usage.extra["cost"] == 0.00015
    assert native.model_inputs["selection_and_arguments"]["provider_payload"] == native_body


def test_stochastic_profile_differs_only_in_temperature():
    det = OpenRouterChatClient(DETERMINISTIC_V1.llm, client=or_client(Recorder()))
    sto = OpenRouterChatClient(STOCHASTIC_V1.llm, client=or_client(Recorder()))
    req = ChatRequest("s", "u", (), "auto")
    a, b = det.build_payload(req), sto.build_payload(req)
    assert a["temperature"] == 0.0 and b["temperature"] == 0.7
    assert {k: v for k, v in a.items() if k != "temperature"} == {k: v for k, v in b.items() if k != "temperature"}
    assert STOCHASTIC_V1.samples_per_condition == 10


# --- matched LLM selector --------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["discrete", "probabilities"])
def test_matched_llm_payload(tasks, mode):
    task = tasks[TASK_ID]
    cset = cset_for(task)
    req = build_selector_request(task.state, cset, ARCHITECTURE_MATCHED_V1)
    target = trusted_candidate(task).candidate_id
    if mode == "discrete":
        answer = {"answers": {"tool": target}}
    else:  # deliberately not summing to 1: must be kept, not normalized
        answer = {"answers": {"tool": {cid: (0.7 if cid == target else 0.05) for cid in req.option_ids}}}
    rec = Recorder(chat_reply(content=json.dumps(answer), finish="stop"))
    selector = MatchedLLMSelector(LLM, answer_mode=mode, client=or_client(rec))
    out = run(selector.select(req))
    (body,) = rec.bodies()
    check_snapshot(f"provider_payload__matched_llm_{mode}__architecture_matched_v1", body)

    assert out.choice == target and out.request_payload == body
    assert body["response_format"]["type"] == "json_schema" and body["response_format"]["json_schema"]["strict"] is True
    assert out.provider_meta["provider"] == "Anthropic" and out.provider_meta["returned_model"] == LLM.model
    if mode == "discrete":
        assert out.probabilities is None and selector.probability_kind is ProbabilityKind.NONE
    else:
        assert out.probabilities == answer["answers"]["tool"]
        assert selector.probability_kind is ProbabilityKind.LLM_VERBALIZED
    schema_text = json.dumps(body["response_format"]["json_schema"]["schema"])
    positions = [schema_text.find(f'"{cid}"' if mode == "probabilities" else f"{cid} = ") for cid in req.option_ids]
    assert all(p >= 0 for p in positions) and positions == sorted(positions)


def test_all_llm_roles_share_one_client_and_identical_parameters(tasks):
    task = tasks[TASK_ID]
    cset = cset_for(task)
    trusted = trusted_candidate(task)
    rec = Recorder(chat_reply(tool_calls=tool_call(trusted.display_name, ARGS)),
                   chat_reply(tool_calls=tool_call(trusted.display_name, ARGS)),
                   chat_reply(content=json.dumps({"answers": {"tool": trusted.candidate_id}}), finish="stop"))
    client = OpenRouterChatClient(LLM, client=or_client(rec))
    run(NativePipeline(client, MockExecutor(), ARCHITECTURE_MATCHED_V1).run(task, order_seed=ORDER_SEED, id_seed=None))
    run(ArgumentGenerator(client).generate(task.state, trusted))
    run(MatchedLLMSelector(LLM, client=client.sdk_client).select(build_selector_request(task.state, cset, ARCHITECTURE_MATCHED_V1)))
    shared = [{k: b.get(k) for k in SHARED_KEYS} for b in rec.bodies()]
    assert len(shared) == 3 and shared[0] == shared[1] == shared[2]
    assert shared[0] == {"model": LLM.model, "temperature": 0.0, "max_tokens": 1024, "reasoning": {"enabled": False},
                         "provider": {"only": ["anthropic"], "allow_fallbacks": False, "require_parameters": True}}


# --- run-aborting conditions -------------------------------------------------------------------------

FATAL_CASES = {
    "provider_mismatch": dict(provider="Amazon Bedrock"),
    "model_mismatch": dict(model="anthropic/claude-haiku-4.5-other"),
    "thinking_not_disabled": dict(reasoning_tokens=42),
}


@pytest.mark.parametrize("kind", sorted(FATAL_CASES))
def test_fatal_conditions_abort_the_native_arm(tasks, kind, tmp_path):
    task = tasks[TASK_ID]
    rec = Recorder(chat_reply(tool_calls=tool_call("send_email", ARGS), **FATAL_CASES[kind]))
    pipeline = NativePipeline(OpenRouterChatClient(LLM, client=or_client(rec)), MockExecutor(), ARCHITECTURE_MATCHED_V1)
    path = tmp_path / "r.jsonl"
    with pytest.raises(FatalRunError) as err:
        run(run_experiment([task], [pipeline], ExperimentConfig("x"), JsonlWriter(path, secrets=())))
    assert err.value.kind == kind
    (abort,) = read_jsonl(path)
    assert abort["record_type"] == "run_aborted" and abort["error_kind"] == kind and abort["pipeline"] == "native_llm"


@pytest.mark.parametrize("kind", sorted(FATAL_CASES))
def test_fatal_conditions_abort_the_matched_arm(tasks, kind):
    """The adapter wraps provider exceptions; fatal conditions must still escape as FatalRunError."""
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    rec = Recorder(chat_reply(content=json.dumps({"answers": {"tool": req.option_ids[0]}}), finish="stop",
                              **FATAL_CASES[kind]))
    with pytest.raises(FatalRunError) as err:
        run(MatchedLLMSelector(LLM, client=or_client(rec)).select(req))
    assert err.value.kind == kind


def test_unroutable_request_aborts_both_llm_paths(tasks):
    task = tasks[TASK_ID]
    no_endpoint = status(404, {"error": {"code": 404, "message": "No endpoints found that can handle the requested parameters."}})
    with pytest.raises(FatalRunError) as err:
        run(OpenRouterChatClient(LLM, client=or_client(Recorder(no_endpoint))).complete(ChatRequest("s", "u", (), "auto")))
    assert err.value.kind == "routing_rejected"
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    with pytest.raises(FatalRunError) as err:
        run(MatchedLLMSelector(LLM, client=or_client(Recorder(no_endpoint))).select(req))
    assert err.value.kind == "routing_rejected"


def test_missing_provider_field_falls_back_to_generation_api(tasks):
    generation = {"data": {"id": "gen-test-123", "provider_name": "Anthropic", "request_id": "req-1727-x",
                           "model": LLM.model}}
    rec = Recorder(chat_reply(content="No tool.", finish="stop", provider=None),
                   routes={"/api/v1/generation": lambda r: httpx2.Response(200, json=generation)})
    resp = run(OpenRouterChatClient(LLM, client=or_client(rec)).complete(ChatRequest("s", "u", (), "auto")))
    assert resp.provider_meta["provider"] == "Anthropic"
    assert resp.provider_meta["provider_source"] == "generation_api"
    assert resp.provider_meta["request_id"] == "req-1727-x"
    gen_req = next(r for r in rec.requests if r.url.path == "/api/v1/generation")
    assert gen_req.url.params["id"] == "gen-test-123"

    generation["data"]["provider_name"] = "Google"
    rec = Recorder(chat_reply(content="No tool.", finish="stop", provider=None),
                   routes={"/api/v1/generation": lambda r: httpx2.Response(200, json=generation)})
    with pytest.raises(FatalRunError, match="provider"):
        run(OpenRouterChatClient(LLM, client=or_client(rec)).complete(ChatRequest("s", "u", (), "auto")))


def test_unverifiable_provider_aborts(tasks):
    rec = Recorder(chat_reply(content="No tool.", finish="stop", provider=None),
                   routes={"/api/v1/generation": status(404)})
    import rlcdselect.llm.openrouter as orm
    original = orm.lookup_generation

    async def fast_lookup(client, gid, attempts=2, delay_s=0.0):
        return await original(client, gid, attempts=attempts, delay_s=delay_s)

    orm.lookup_generation = fast_lookup
    try:
        with pytest.raises(FatalRunError) as err:
            run(OpenRouterChatClient(LLM, client=or_client(rec)).complete(ChatRequest("s", "u", (), "auto")))
    finally:
        orm.lookup_generation = original
    assert err.value.kind == "provider_mismatch"


# --- Jev via OpenRouter System One ------------------------------------------------------------------

@pytest.mark.parametrize("condition,cfg", [("architecture_matched_v1", ARCHITECTURE_MATCHED_V1),
                                           ("ecological_name_description_v1", ECOLOGICAL_NAME_DESCRIPTION_V1)])
def test_jev_payload(tasks, condition, cfg):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task, cfg), cfg)
    probs = {cid: (0.97 if i == 0 else 0.01) for i, cid in enumerate(req.option_ids)}
    rec = Recorder(jev_reply(req.option_ids[0], probs))
    out = run(JevSelector(client=ts_client(rec)).select(req))
    (body,) = rec.bodies()
    check_snapshot(f"provider_payload__jev__{condition}", body)

    assert str(rec.requests[0].url) == "https://openrouter.ai/api/v1/systemone"
    assert body["model"] == "typesafe/jev-1.13" == JEV_MODEL
    assert body["state"] == dict(req.state)
    criteria = body["questions"]["tool"]["criteria"]
    assert list(criteria) == list(req.option_ids)
    assert criteria == json.loads(json.dumps(dict(req.criteria)))
    assert out.request_payload == body and out.probabilities == probs
    assert out.provider_meta == {"gateway": "openrouter", "requested_model": "typesafe/jev-1.13",
                                 "returned_model": JEV_BUILD, "provider": "TypeSafe", "provider_source": "response",
                                 "generation_id": "gen-dec-test", "request_id": None, "cost": 0.0000126}


def test_jev_and_matched_llm_receive_the_same_options(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    jev_rec = Recorder(jev_reply(req.option_ids[0], {cid: 1 / len(req.option_ids) for cid in req.option_ids}))
    llm_rec = Recorder(chat_reply(content=json.dumps({"answers": {"tool": req.option_ids[0]}}), finish="stop"))
    run(JevSelector(client=ts_client(jev_rec)).select(req))
    run(MatchedLLMSelector(LLM, client=or_client(llm_rec)).select(req))
    jev_body, llm_body = jev_rec.bodies()[0], llm_rec.bodies()[0]
    schema = llm_body["response_format"]["json_schema"]["schema"]
    enum = schema["$defs"]["TypeSafeAnswers"]["properties"]["tool"]["enum"]
    assert enum == list(jev_body["questions"]["tool"]["criteria"]) == list(req.option_ids)


@pytest.mark.parametrize("model", ["jev-latest", "~typesafe/jev-latest", "typesafe/jev-latest"])
def test_jev_refuses_unpinned_models(model):
    with pytest.raises(ValueError, match="pinned"):
        JevSelector(model, client=ts_client(Recorder()))


@pytest.mark.parametrize("kind,reply", [
    ("model_mismatch", dict(model="typesafe/jev-1.14-20261101")),
    ("provider_mismatch", dict(provider="SomeoneElse")),
])
def test_jev_fatal_conditions(tasks, kind, reply):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    rec = Recorder(jev_reply(req.option_ids[0], {cid: 0.25 for cid in req.option_ids}, **reply))
    with pytest.raises(FatalRunError) as err:
        run(JevSelector(client=ts_client(rec)).select(req))
    assert err.value.kind == kind


def test_jev_unroutable_is_fatal(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    with pytest.raises(FatalRunError) as err:
        run(JevSelector(client=ts_client(Recorder(status(404)))).select(req))
    assert err.value.kind == "routing_rejected"


def test_jev_malformed_probabilities_flow_through_unchanged(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    probs = {cid: 0.2 for cid in req.option_ids}  # sums to 0.8
    pipeline = DecomposedPipeline(JevSelector(client=ts_client(Recorder(jev_reply(req.option_ids[0], probs)))),
                                  ArgumentGenerator(OpenRouterChatClient(LLM, client=or_client(Recorder()))),
                                  MockExecutor(), ARCHITECTURE_MATCHED_V1)
    pipeline.argument_generator.generate = _no_arguments
    outcome = run(pipeline.run(task, order_seed=ORDER_SEED, id_seed=None))
    assert dict(outcome.selection.probabilities) == probs
    assert any(i.startswith("sum=0.8") for i in outcome.selection.probability_issues)


async def _no_arguments(state, candidate):
    from rlcdselect.pipelines.base import SKIPPED_ARGUMENTS
    return SKIPPED_ARGUMENTS, None, None


# --- no hidden SDK retries ---------------------------------------------------------------------------

def test_sdk_level_retries_are_disabled(tasks):
    task = tasks[TASK_ID]
    req = build_selector_request(task.state, cset_for(task), ARCHITECTURE_MATCHED_V1)
    jev_rec = Recorder(status(429), status(200))
    with pytest.raises(TransientError):
        run(JevSelector(client=ts_client(jev_rec)).select(req))
    assert len(jev_rec.requests) == 1

    llm_rec = Recorder(status(500), status(200))
    with pytest.raises(TransientError):
        run(MatchedLLMSelector(LLM, client=or_client(llm_rec)).select(req))
    assert len(llm_rec.requests) == 1

    native_rec = Recorder(status(429), status(200))
    outcome = run(NativePipeline(OpenRouterChatClient(LLM, client=or_client(native_rec)), MockExecutor(),
                                 ARCHITECTURE_MATCHED_V1).run(task, order_seed=ORDER_SEED, id_seed=None))
    assert outcome.selection.status is SelectionStatus.ERROR
    assert outcome.selection.error.kind == "transient" and len(native_rec.requests) == 1


def test_client_rejects_sdk_retries():
    with pytest.raises(ValueError, match="max_retries=0"):
        OpenRouterChatClient(LLM, client=openai.AsyncOpenAI(api_key="x", base_url="https://openrouter.ai/api/v1"))


# --- startup checks (OpenRouter endpoint listing) -------------------------------------------------------

def endpoints_reply(endpoints):
    return lambda r: httpx2.Response(200, json={"data": {"id": "m", "endpoints": endpoints}})


ANTHROPIC = {"provider_name": "Anthropic", "tag": "anthropic",
             "supported_parameters": ["reasoning", "max_tokens", "temperature", "tools", "tool_choice",
                                      "structured_outputs", "response_format"]}
BEDROCK = {"provider_name": "Amazon Bedrock", "tag": "amazon-bedrock/us", "supported_parameters": ANTHROPIC["supported_parameters"]}
JEV_ENDPOINT = {"provider_name": "TypeSafe", "tag": "typesafe", "supported_parameters": []}


def catalog(routes):
    return OpenRouterCatalog(http=httpx2.AsyncClient(transport=httpx2.MockTransport(Recorder(routes=routes))))


def test_startup_checks_pass_and_fail_loudly():
    ok = {f"/api/v1/models/{LLM.model}/endpoints": endpoints_reply([BEDROCK, ANTHROPIC]),
          f"/api/v1/models/{JEV_MODEL}/endpoints": endpoints_reply([JEV_ENDPOINT])}
    cat = catalog(ok)
    jev = JevSelector(client=ts_client(Recorder()), catalog=cat)
    verified = run(verify_live_models(LLM, jev, cat))
    assert verified["llm"]["tag"] == "anthropic" and verified["jev"]["provider"] == "TypeSafe"

    no_anthropic = dict(ok, **{f"/api/v1/models/{LLM.model}/endpoints": endpoints_reply([BEDROCK])})
    with pytest.raises(ModelUnavailableError, match="Amazon Bedrock"):
        run(verify_live_models(LLM, None, catalog(no_anthropic)))

    no_temp = dict(ANTHROPIC, supported_parameters=[p for p in ANTHROPIC["supported_parameters"] if p != "temperature"])
    missing_param = dict(ok, **{f"/api/v1/models/{LLM.model}/endpoints": endpoints_reply([no_temp])})
    with pytest.raises(ModelUnavailableError, match="temperature"):
        run(verify_live_models(LLM, None, catalog(missing_param)))

    no_jev = dict(ok, **{f"/api/v1/models/{JEV_MODEL}/endpoints": status(404)})
    cat = catalog(no_jev)
    with pytest.raises(ModelUnavailableError, match="jev-1.13"):
        run(verify_live_models(LLM, JevSelector(client=ts_client(Recorder()), catalog=cat), cat))
    assert set(SHARED_LLM_REQUIRED_PARAMETERS) <= set(ANTHROPIC["supported_parameters"])


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
