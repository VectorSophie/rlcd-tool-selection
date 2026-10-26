import json
import math
import os
import re
import subprocess
from pathlib import Path

import pytest
from conftest import run

from rlcdselect.core.serialization import ABSTAIN_ID, Representation, SerializationConfig
from rlcdselect.core.types import ABSTAIN, LLMConfig, ProbabilityKind
from rlcdselect.eval.logging import REDACTED, JsonlWriter, read_jsonl, redact, secret_values_from_env
from rlcdselect.eval.metrics import (
    IncomparableProbabilitiesError,
    js_divergence,
    probability_shift,
    selection_frequencies,
    summarize,
    total_variation,
)
from rlcdselect.eval.replay import logged_selection_input, rebuild_selection_input, task_from_record
from rlcdselect.eval.runner import ExperimentConfig, InvariantError, check_invariants, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import KeywordChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.selectors.mock import KeywordSelector, ScriptedSelector, output

REPO = Path(__file__).resolve().parents[1]


def offline_arms(serialization, llm=None):
    llm = llm or KeywordChatClient()
    executor = MockExecutor()
    return [
        NativePipeline(llm, executor, serialization),
        DecomposedPipeline(KeywordSelector(), ArgumentGenerator(llm), executor, serialization),
    ]


def test_complete_offline_run_writes_valid_records(core, serialization, tmp_path):  # required test 15
    tasks = core
    path = tmp_path / "run.jsonl"
    config = ExperimentConfig("test", order_seeds=(None, 4))
    records = run(run_experiment(tasks, offline_arms(serialization), config, JsonlWriter(path, secrets=())))
    assert len(records) == len(tasks) * 2 * 2
    assert read_jsonl(path) == [json.loads(json.dumps(r)) for r in records]
    assert len({r["run_id"] for r in records}) == len(records)
    for r in records:
        assert r["selection_status"] in {"selected", "abstained", "multiple_tool_calls", "error"}
        assert r["selection_label"] == (r["selected_tool"] if r["selection_status"] == "selected"
                                        else ABSTAIN if r["selection_status"] == "abstained" else None)


def test_records_are_sufficient_to_reproduce_inputs(core, serialization, tmp_path):  # required test 14
    tasks = core
    path = tmp_path / "run.jsonl"
    for rep in Representation:
        cfg = SerializationConfig(representation=rep, name_policy=serialization.name_policy)
        run(run_experiment(tasks, offline_arms(cfg), ExperimentConfig(f"repro-{rep.value}", order_seeds=(3,), id_seed=8),
                           JsonlWriter(path, secrets=())))
    for record in read_jsonl(path):
        assert task_from_record(record).task_id == record["task_id"]
        # Compare serialized text, not dicts: dict equality would ignore criteria order.
        assert json.dumps(rebuild_selection_input(record)) == json.dumps(logged_selection_input(record))
        if not record["native_single_call"]:
            criteria_order = [k for k in logged_selection_input(record)["criteria"] if k != ABSTAIN_ID]
            assert criteria_order == logged_selection_input(record)["candidate_ids"]
            assert [record["candidate_ids"][c] for c in criteria_order] == record["tool_order"]


def test_invariants_reject_mismatched_llms_and_serializations(serialization):
    a = KeywordChatClient(LLMConfig("openai", "model-a", temperature=0.0))
    b = KeywordChatClient(LLMConfig("openai", "model-a", temperature=0.7))
    with pytest.raises(InvariantError, match="LLM"):
        check_invariants([NativePipeline(a, MockExecutor(), serialization),
                          DecomposedPipeline(KeywordSelector(), ArgumentGenerator(b), MockExecutor(), serialization)])
    other = SerializationConfig(representation=Representation.NAME_ONLY, name_policy=serialization.name_policy)
    with pytest.raises(InvariantError, match="serialization"):
        check_invariants([NativePipeline(a, MockExecutor(), serialization),
                          DecomposedPipeline(KeywordSelector(), ArgumentGenerator(a), MockExecutor(), other)])
    check_invariants(offline_arms(serialization))


def test_redaction_of_secret_keys_and_values():
    secrets = secret_values_from_env({"OPENAI_API_KEY": "sk-test-1234567890", "TYPESAFE_API_KEY": "short"})
    assert secrets == ("sk-test-1234567890",)
    record = {"raw": {"headers": {"Authorization": "Bearer sk-test-1234567890"}, "api_key": "x",
                      "text": "echo sk-test-1234567890", "usage": {"input_tokens": 3}}}
    out = redact(record, secrets)
    assert out["raw"]["headers"]["Authorization"] == REDACTED and out["raw"]["api_key"] == REDACTED
    assert out["raw"]["text"] == f"echo {REDACTED}"
    assert out["raw"]["usage"] == {"input_tokens": 3}  # token counts are not secrets


def test_writer_scrubs_secrets(tmp_path):
    path = tmp_path / "r.jsonl"
    JsonlWriter(path, secrets=["sk-live-abcdefgh"]).write({"note": "key sk-live-abcdefgh leaked"})
    assert "sk-live-abcdefgh" not in path.read_text()


_SECRET_PATTERNS = [re.compile(p) for p in (r"sk-[A-Za-z0-9_-]{20,}", r"sk-ant-[A-Za-z0-9_-]{20,}", r"AIza[0-9A-Za-z_-]{30,}")]


def test_no_secrets_in_repository():  # required test 16
    # Every file git would commit (tracked, or untracked and not ignored). A key in the git-ignored
    # .env is the intended setup; the last assertion checks that .env stays ignored.
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            cwd=REPO, capture_output=True, check=True).stdout.decode().split("\0")
    offenders = []
    for name in filter(None, listed):
        path = REPO / name
        if not path.is_file() or name.startswith("results/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(p.search(text) for p in _SECRET_PATTERNS):
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders
    assert ".env" not in listed
    assert not (REPO / ".env").exists() or ".env" in (REPO / ".gitignore").read_text()


# --- metrics ---------------------------------------------------------------------------------------

def test_distribution_measures():
    p, q = {"a": 1.0}, {"b": 1.0}
    assert total_variation(p, q) == 1.0 and math.isclose(js_divergence(p, q), 1.0)
    assert total_variation(p, p) == 0.0 and js_divergence(p, p) == 0.0


def _prob_records(tasks, serialization, kind, seeds, selector_id="jev"):
    task = tasks["attacker_preference_wording"]

    def answer(req):
        ids = req.candidate_ids
        return output(ids[0], {ids[0]: 0.6, ids[1]: 0.3, ids[2]: 0.05, ABSTAIN_ID: 0.05})

    selector = ScriptedSelector([answer] * len(seeds), selector_id=selector_id, probability_kind=kind)
    arm = DecomposedPipeline(selector, ArgumentGenerator(KeywordChatClient()), MockExecutor(), serialization)
    return run(run_experiment([task], [arm], ExperimentConfig("p", order_seeds=seeds)))


def test_probability_shift_within_selector_aligns_by_tool(tasks, serialization):
    clean, perturbed = _prob_records(tasks, serialization, ProbabilityKind.RLCD_NATIVE, (None, 5))
    shift = probability_shift(clean, perturbed)
    assert shift["probability_kind"] == "rlcd_native"
    assert set(shift["delta"]) == set(clean["selection_probabilities_by_tool"]) | set(perturbed["selection_probabilities_by_tool"])
    assert math.isclose(sum(shift["delta"].values()), 0.0, abs_tol=1e-9)


def test_probability_shift_refuses_cross_selector_comparison(tasks, serialization):
    (jev,) = _prob_records(tasks, serialization, ProbabilityKind.RLCD_NATIVE, (None,), selector_id="jev")
    (llm,) = _prob_records(tasks, serialization, ProbabilityKind.LLM_VERBALIZED, (None,), selector_id="matched_llm")
    with pytest.raises(IncomparableProbabilitiesError):
        probability_shift(jev, llm)


def test_probability_shift_refuses_selectors_without_probabilities(fixtures, serialization):
    _, tasks = fixtures
    records = run(run_experiment(tasks[:1], offline_arms(serialization), ExperimentConfig("x", order_seeds=(None, 1))))
    native = [r for r in records if r["pipeline"] == "native_llm"]
    with pytest.raises(IncomparableProbabilitiesError):
        probability_shift(native[0], native[1])


def test_summary_and_frequencies_use_discrete_outcomes(core, serialization):
    tasks = core
    records = run(run_experiment(tasks, offline_arms(serialization), ExperimentConfig("s", order_seeds=(None, 1, 2))))
    summary = summarize(records)
    assert set(summary) == {"native_llm", "mock_keyword"}
    for s in summary.values():
        assert math.isclose(sum(s["role_selection_rates"].values()), 1.0)
    for dist in selection_frequencies(records).values():
        assert math.isclose(sum(dist.values()), 1.0)


def test_duplicate_name_stress_is_decomposed_only(fixtures):
    from rlcdselect.datasets.fixtures import decomposed_only_tasks
    from rlcdselect.profiles import DUPLICATE_NAME_STRESS_V1

    llm = KeywordChatClient()
    native = NativePipeline(llm, MockExecutor(), DUPLICATE_NAME_STRESS_V1)
    decomposed = DecomposedPipeline(KeywordSelector(), ArgumentGenerator(llm), MockExecutor(), DUPLICATE_NAME_STRESS_V1)
    with pytest.raises(InvariantError, match="decomposed-only"):
        check_invariants([native, decomposed])
    stress = decomposed_only_tasks(fixtures[1])
    records = run(run_experiment(stress, [decomposed], ExperimentConfig("stress", condition="duplicate_name_stress_v1")))
    assert records and all(r["selection_status"] != "error" for r in records)
    assert all(r["condition"] == "duplicate_name_stress_v1" for r in records)


def test_load_dotenv_never_overrides_and_returns_names_only(tmp_path, monkeypatch):
    from rlcdselect.startup import load_dotenv

    env = tmp_path / ".env"
    env.write_text('# comment\nRLCD_A="quoted-a"\nexport RLCD_B=b\nRLCD_C=\nRLCD_D=from-file\n', encoding="utf-8")
    monkeypatch.delenv("RLCD_A", raising=False)
    monkeypatch.delenv("RLCD_B", raising=False)
    monkeypatch.delenv("RLCD_C", raising=False)
    monkeypatch.setenv("RLCD_D", "from-shell")
    assert load_dotenv(env) == ["RLCD_A", "RLCD_B"]
    assert (os.environ["RLCD_A"], os.environ["RLCD_B"], os.environ["RLCD_D"]) == ("quoted-a", "b", "from-shell")
    assert "RLCD_C" not in os.environ
    assert load_dotenv(tmp_path / "missing.env") == []
