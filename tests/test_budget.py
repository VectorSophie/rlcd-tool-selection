import pytest
from conftest import run
from helpers import call, response

from rlcdselect.core.types import FatalRunError
from rlcdselect.eval.budget import DEFAULT_PRICES, BudgetGuard, Prices, estimate_run_cost, prices_from_catalog
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.llm.base import ChatResponse
from rlcdselect.llm.fake import ScriptedChatClient
from rlcdselect.pipelines.native import NativePipeline


def costly(cost: float):
    """A scripted LLM reply (abstain) whose provider metadata reports `cost` USD."""
    base = response(text="no tool")
    return lambda request: ChatResponse(base.tool_calls, base.text, base.usage, base.model_reported, base.raw,
                                        provider_meta={"provider": "Anthropic", "cost": cost})


def test_estimate_scales_and_refuses_over_cap(core, serialization):
    one = estimate_run_cost(core, ["native_llm", "matched_llm", "jev"], serialization, DEFAULT_PRICES, 1, 1)
    three = estimate_run_cost(core, ["native_llm", "matched_llm", "jev"], serialization, DEFAULT_PRICES, 3, 1)
    assert three["total_usd"] == pytest.approx(3 * one["total_usd"])
    assert one["per_pipeline_usd"]["jev"] < one["per_pipeline_usd"]["native_llm"]  # Jev selection is ~free
    assert 0.005 < one["total_usd"] < 0.5  # sanity: 14 tasks x 3 arms on Haiku 4.5
    with pytest.raises(FatalRunError, match="exceeds the cap"):
        BudgetGuard(cap_usd=one["total_usd"] / 2).check_estimate(one)
    BudgetGuard(cap_usd=one["total_usd"] * 2).check_estimate(one)


def test_charge_prefers_reported_cost_and_falls_back_to_tokens():
    guard = BudgetGuard(cap_usd=1.0, prices=Prices(llm_input=1e-6, llm_output=5e-6, jev_input=0.042e-6))
    reported = {"pipeline": "jev", "selector_id": "jev", "selection_provider_meta": {"cost": 0.00001},
                "argument_provider_meta": {"cost": 0.0002}}
    assert guard.charge(reported) == pytest.approx(0.00021)
    no_cost = {"pipeline": "native_llm", "selector_id": "native_llm", "selection_provider_meta": {"cost": None},
               "selector_usage": {"input_tokens": 1000, "output_tokens": 100}}
    assert guard.charge(no_cost) == pytest.approx(1000e-6 + 100 * 5e-6)
    matched_multi = {"pipeline": "matched_llm", "selector_id": "matched_llm",
                     "selection_provider_meta": {"calls": [{"cost": 0.001}, {"cost": 0.002}]}}
    assert guard.charge(matched_multi) == pytest.approx(0.003)
    local = {"pipeline": "laya", "selector_id": "laya", "selector_usage": {"input_tokens": 5000, "output_tokens": 0}}
    assert guard.charge(local) == 0.0  # local selectors are free
    s = guard.summary()
    assert s["reported_usd"] == pytest.approx(0.00021 + 0.003)
    assert s["token_estimated_usd"] == pytest.approx(1000e-6 + 100 * 5e-6)


def test_run_stops_when_spend_reaches_cap(core, serialization, tmp_path):
    tasks = core[:5]
    llm = ScriptedChatClient([costly(0.4)] * 5)
    pipeline = NativePipeline(llm, MockExecutor(), serialization)
    path = tmp_path / "r.jsonl"
    guard = BudgetGuard(cap_usd=1.0)
    with pytest.raises(FatalRunError, match="reached the cap"):
        run(run_experiment(tasks, [pipeline], ExperimentConfig("b"), JsonlWriter(path, secrets=()), budget=guard))
    lines = read_jsonl(path)
    assert [line["record_type"] for line in lines] == ["run", "run", "run", "run_aborted"]
    assert lines[-1]["error_kind"] == "budget_exceeded"
    assert lines[2]["budget_spent_usd"] == pytest.approx(1.2)
    assert len(llm.requests) == 3  # no call after the cap was reached


def test_fatal_abort_still_charges_the_billed_call(core, serialization, tmp_path):
    def mismatch(request):
        raise FatalRunError("model_mismatch", "x", raw={"cost": 0.05, "returned_model": "other"})

    pipeline = NativePipeline(ScriptedChatClient([mismatch]), MockExecutor(), serialization)
    guard = BudgetGuard(cap_usd=1.0)
    with pytest.raises(FatalRunError):
        run(run_experiment(core[:1], [pipeline], ExperimentConfig("f"), JsonlWriter(tmp_path / "r.jsonl", secrets=()),
                           budget=guard))
    assert guard.spent_usd == pytest.approx(0.05)
    (abort,) = read_jsonl(tmp_path / "r.jsonl")
    assert abort["budget"]["spent_usd"] == pytest.approx(0.05)


def test_prices_from_catalog():
    p = prices_from_catalog({"pricing": {"prompt": "0.000001", "completion": "0.000005"}},
                            {"pricing": {"prompt": "0.000000042"}})
    assert (p.llm_input, p.llm_output, p.jev_input, p.source) == (1e-6, 5e-6, 4.2e-8, "openrouter_endpoints")
