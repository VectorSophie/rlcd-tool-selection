"""External pilot path: dataset registry, sampling, manifests, budget gating and execution.

Uses synthetic adapter results injected into the registry's loader, so no dataset is downloaded.
"""

import json

import pytest
from conftest import run

from rlcdselect.core.serialization import ABSTAIN_ID, present_task
from rlcdselect.core.types import ABSTAIN
from rlcdselect.datasets.external import bfcl, metatool, registry, when2call
from rlcdselect.datasets.external.registry import DATASETS, SamplingError, sample_dataset
from rlcdselect.eval import pilot
from rlcdselect.eval.budget import DEFAULT_PRICES
from rlcdselect.eval.pilot_analysis import analyze, mcnemar_exact, paired_native_matched, wilson
from rlcdselect.eval.runner import ExperimentConfig, InvariantError, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import KeywordChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import DETERMINISTIC_V1
from rlcdselect.selectors.base import SelectorOutput
from rlcdselect.core.types import ProbabilityKind, Usage

# --- synthetic sources ---------------------------------------------------------------------

LAMP = {"name": "home.set_lamp", "description": "Turn a smart lamp on or off.",
        "parameters": {"type": "dict", "required": ["room"], "properties": {"room": {"type": "string"}}}}
FAN = {"name": "home.set_fan", "description": "Set a ceiling fan speed.",
       "parameters": {"type": "dict", "required": ["speed"], "properties": {"speed": {"type": "integer"}}}}


def w2c_rows(groups=60):
    rows = []
    for g in range(groups):
        base = {"source": "synthetic", "source_id": f"grp-{g}", "question": f"Turn on the lamp in room {g}.",
                "answers": {"tool_call": json.dumps({"name": "home.set_lamp", "arguments": {"room": str(g)}})}}
        rows += [
            {**base, "uuid": f"c{g}", "correct_answer": "tool_call", "tools": [json.dumps(FAN), json.dumps(LAMP)],
             "target_tool": json.dumps(LAMP)},
            {**base, "uuid": f"r{g}", "correct_answer": "request_for_info", "tools": [json.dumps(FAN), json.dumps(LAMP)],
             "target_tool": json.dumps(LAMP), "held_out_param": "room"},
            {**base, "uuid": f"n{g}", "correct_answer": "cannot_answer", "tools": [json.dumps(FAN)], "target_tool": None},
        ]
    return rows


def mt_rows(n=30):
    names = [f"Tool{i}" for i in range(10)]
    prompt = ("[List of Tools with Names and Descriptions Start]\n" +
              "\n".join(f"{i + 1}. tool name: {nm}, tool description: ['Does thing {i}.']" for i, nm in enumerate(names)) +
              "\n[List of Tools with Names and Descriptions End]")
    return [{"query": f"Please do thing zero, request {k}.", "tool": "Tool0", "index": k, "action_prompt": prompt,
             "thought_prompt": ""} for k in range(n)]


def bfcl_rows(n=40):
    rows, answers = [], []
    area = {"name": "geo.area", "description": "Rectangle area.",
            "parameters": {"type": "dict", "required": ["w", "h"],
                           "properties": {"w": {"type": "integer"}, "h": {"type": "integer"},
                                          "unit": {"type": "string", "enum": ["m", "cm"]}}}}
    for i in range(n):
        rows.append({"id": f"live_simple_{i}", "question": [[{"role": "user", "content": f"Area of {i} by 3?"}]],
                     "function": [area]})
        gt = {"w": [i], "h": [3], "unit": ["m", ""]}
        if i % 10 == 1:
            gt["unit"] = ["N/A"]  # literal N/A gold (also outside the enum)
        elif i % 10 == 2:
            gt["w"] = [str(i)]  # schema-inconsistent gold (string for integer)
        elif i % 10 == 3:
            gt["unit"] = []  # undocumented empty alternative list
        answers.append({"id": f"live_simple_{i}", "ground_truth": [{"geo.area": gt}]})
    return rows, answers


@pytest.fixture
def synthetic(monkeypatch):
    rows, answers = bfcl_rows()
    sources = {
        "when2call": when2call.adapt(w2c_rows()),
        "metatool:Task2-Subtask1": metatool.adapt(mt_rows(), "Task2-Subtask1"),
        "metatool:Task2-Subtask3": metatool.adapt([dict(r, tool="Missing") for r in mt_rows()], "Task2-Subtask3"),
        "bfcl:live_simple": bfcl.adapt(rows, "live_simple", answers),
        "bfcl:simple_python": bfcl.adapt([], "simple_python"),
        "bfcl:multiple": bfcl.adapt([], "multiple"),
        "bfcl:live_multiple": bfcl.adapt([], "live_multiple"),
        "bfcl:irrelevance": bfcl.adapt([{"id": f"irrelevance_{i}", "question": [[{"role": "user", "content": "Tell a joke."}]],
                                         "function": [LAMP]} for i in range(20)], "irrelevance"),
    }
    monkeypatch.setattr(registry, "_load", lambda src: sources[src])
    return sources


# 1
def test_bfcl_diagnostic_items_never_enter_primary_sampling(synthetic):
    sample = sample_dataset("bfcl_live_simple", 28, seed=1)
    for t in sample.tasks:
        assert not set(t.tags) & set(registry.QUALITY_FLAGS)
    assert sample.info["eligible"] == 28  # 40 rows, 12 flagged
    assert sample.info["not_eligible_by_reason"] == {"bfcl_ambiguous_empty_alternative": 4, "bfcl_na_gold": 4,
                                                     "bfcl_schema_inconsistent": 8}
    with pytest.raises(SamplingError):
        sample_dataset("bfcl_live_simple", 29, seed=1)
    diag = {name: sample_dataset(name, None, seed=1) for name in registry.QUALITY_FLAGS.values()}
    assert {n: len(s.tasks) for n, s in diag.items()} == {"bfcl_schema_inconsistent": 8, "bfcl_na_gold": 4,
                                                          "bfcl_ambiguous_empty_alternative": 4}
    assert all(DATASETS[n].role == "diagnostic" for n in diag)
    items = registry.diagnostic_items()
    assert len(items) == 12 and all(i["original_gold"] and i["gold_tool_schema"] for i in items)
    na = next(i for i in items if i["source_item_id"] == "live_simple_1")
    assert set(na["exclusion_reasons"]) == {"bfcl_na_gold", "bfcl_schema_inconsistent"}


# 2, 11
def test_when2call_stratified_counts_and_clusters(synthetic):
    s = sample_dataset("when2call", 150, seed=7)
    assert s.info["sampled_by_label"] == {"cannot_answer": 50, "request_for_info": 50, "tool_call": 50}
    assert all(t.provenance["source_group_id"].startswith("grp-") for t in s.tasks)
    assert {t.expected.abstain_reason for t in s.tasks} == {None, "missing_information", "no_suitable_tool"}
    with pytest.raises(SamplingError, match="stratified size"):
        sample_dataset("when2call", 120, seed=7)
    plan = pilot.plan_group("A", [("when2call", 150)], seed=7, stratify=True, profile=DETERMINISTIC_V1,
                            jev_repetitions=10, prices=DEFAULT_PRICES)
    clusters = plan["datasets"][0]["cluster_ids"]
    assert len(clusters) == 150 and set(clusters.values()) <= {f"grp-{g}" for g in range(60)}


# 3
def test_metatool_source_order_is_not_the_presentation_order(synthetic, serialization):
    s = sample_dataset("metatool_s1", 30, seed=3)
    assert all(t.provenance["source_gold_position"] == 0 for t in s.tasks)
    seeds = list(s.order_seeds.values())
    assert None not in seeds and len(set(seeds)) == len(seeds)  # one distinct seed per task
    positions = {present_task(t, DATASETS["metatool_s1"] and serialization, order_seed=s.order_seeds[t.task_id],
                              id_seed=None).tool_order.index("metatool/Tool0") for t in s.tasks}
    assert len(positions) > 3  # the gold no longer sits at one fixed position
    selector = _Fixed("matched_llm", lambda req: req.abstain_id)
    pipe = DecomposedPipeline(selector, ArgumentGenerator(KeywordChatClient()), MockExecutor(), serialization)
    with pytest.raises(InvariantError):
        run(run_experiment(list(s.tasks), [pipe], ExperimentConfig("x")))  # source order only: refused


# 4
def test_samples_are_reproducible_from_the_seed(synthetic):
    a, b = sample_dataset("metatool_s3", 20, seed=11), sample_dataset("metatool_s3", 20, seed=11)
    assert [t.task_id for t in a.tasks] == [t.task_id for t in b.tasks] and a.order_seeds == b.order_seeds
    c = sample_dataset("metatool_s3", 20, seed=12)
    assert [t.task_id for t in a.tasks] != [t.task_id for t in c.tasks]


def _frozen(tmp_path, datasets, **kw):
    plan = pilot.plan_group("T", datasets, seed=5, stratify=True, profile=DETERMINISTIC_V1, jev_repetitions=10,
                            prices=DEFAULT_PRICES)
    pilot.allocate_caps([plan], **kw)
    path = pilot.freeze(plan, tmp_path / "T", allow_dirty=True)
    return json.loads(path.read_text())


# 5
def test_manifest_reproduces_exact_task_ids(synthetic, tmp_path):
    m = _frozen(tmp_path, [("metatool_s1", 10), ("bfcl_live_simple", 8)])
    samples = pilot.verify_manifest(m, DEFAULT_PRICES, check_git=False)
    assert [[t.task_id for t in s.tasks] for s in samples] == [d["task_ids"] for d in m["datasets"]]
    assert m["manifest_hash"] == pilot.manifest_hash(m) and m["jev"]["selector_repetitions"] == 10
    for key in ("git_commit", "seed", "profile", "llm_config", "prices", "budget_cap_usd", "created_at"):
        assert key in m
    assert m["datasets"][0]["sources"][0]["adapter_version"] == "metatool_v1"
    edited = json.loads(json.dumps(m))
    edited["datasets"][0]["task_ids"][0] = "metatool:other"
    with pytest.raises(pilot.PlanError, match="hash mismatch"):
        pilot.verify_manifest(edited, check_git=False)
    edited["manifest_hash"] = pilot.manifest_hash(edited)
    with pytest.raises(pilot.PlanError, match="re-derived sample differs"):
        pilot.verify_manifest(edited, check_git=False)
    with pytest.raises(pilot.PlanError, match="never overwritten"):
        pilot.freeze({**m, "manifest_hash": None}, tmp_path / "T", allow_dirty=True)


class _Fixed:
    """A selector stand-in with a fixed id; `choose(request)` returns an option id."""

    def __init__(self, selector_id, choose, kind=ProbabilityKind.NONE, probs=None):
        self._id, self.choose, self._kind, self.probs = selector_id, choose, kind, probs
        self.requests = []

    selector_id = property(lambda self: self._id)
    model = property(lambda self: "fake")
    probability_kind = property(lambda self: self._kind)
    llm_config = property(lambda self: None)

    async def select(self, request):
        self.requests.append(request)
        n = len(self.requests)
        choice = self.choose(request) if callable(self.choose) else self.choose
        probs = self.probs(request, n) if self.probs else None
        return SelectorOutput(choice, probs, None, Usage(10, 0), "fake", raw={"n": n},
                              provider_meta={"generation_id": f"{self._id}-{n}", "cost": 0.0})


def _factory(log):
    llm = KeywordChatClient()
    log["llm"] = llm

    def first_option(req):
        return next(k for k in req.criteria if k != req.abstain_id)

    def jev_probs(req, n):
        opts = list(req.criteria)
        return {k: (0.6 if k == opts[0] else 0.4 / (len(opts) - 1)) for k in opts}

    def make(serialization, jev_sampling):
        matched = _Fixed("matched_llm", first_option)
        # Jev alternates: odd calls pick the first option, even calls abstain.
        jev = _Fixed("jev", lambda req: first_option(req) if len(jev.requests) % 2 else req.abstain_id,
                     kind=ProbabilityKind.RLCD_NATIVE, probs=jev_probs)
        log.setdefault("jev", []).append(jev)
        log.setdefault("serializations", []).append(serialization)
        executor = MockExecutor()
        args = ArgumentGenerator(llm)
        return [NativePipeline(llm, executor, serialization), DecomposedPipeline(matched, args, executor, serialization),
                DecomposedPipeline(jev, args, executor, serialization, sampling=jev_sampling)]
    return make


# 6, 7, 10, 12
def test_execution_uses_ten_jev_draws_and_only_the_designated_one_continues(synthetic, tmp_path):
    m = _frozen(tmp_path, [("metatool_s1", 4), ("bfcl_live_simple", 3)])
    samples = pilot.verify_manifest(m, DEFAULT_PRICES, check_git=False)
    log = {}
    records, budget = run(pilot.execute_group(m, samples, _factory(log), tmp_path / "T" / "records.jsonl",
                                              prices=DEFAULT_PRICES))
    jev_records = [r for r in records if r["pipeline"] == "jev"]
    assert len(jev_records) == 7
    assert sum(len(j.requests) for j in log["jev"]) == 70  # 10 draws per task
    for r in jev_records:
        assert len(r["selector_samples"]) == 10 and r["execution_sample_index"] == 0
        assert [s["used_for_execution"] for s in r["selector_samples"]] == [True] + [False] * 9
        assert r["selection_label"] == r["selector_samples"][0]["selection_label"]  # draw 0, not the majority
        assert r["selector_sample_summary"]["choice_flip_rate"] > 0
    # Argument generation ran once per arm-task that selected a tool, never once per draw.
    arg_calls = [q for q in log["llm"].requests if q.tool_choice != "auto"]
    selected = [r for r in records if r["pipeline"] != "native_llm" and r["selection_status"] == "selected"]
    assert len(arg_calls) == len(selected)
    # Dataset conditions are explicit and applied (MetaTool: name + description text; BFCL: schema objects).
    assert {r["dataset"]: r["condition"] for r in records} == {
        "metatool_s1": "ecological_name_description_v1", "bfcl_live_simple": "architecture_matched_v1"}
    assert [s.representation.value for s in log["serializations"]] == ["name_description", "name_description_schema"]
    assert {r["manifest_hash"] for r in records} == {m["manifest_hash"]}
    assert all(r["order_seed"] == m["datasets"][0 if r["dataset"] == "metatool_s1" else 1]["order_seeds"][r["task_id"]]
               for r in records)
    summary = analyze(records, [m])
    pairs = summary["datasets"]["bfcl_live_simple"]["native_vs_matched"]
    assert pairs["n_pairs"] == 3 and sum(pairs["counts"].values()) == 3
    with pytest.raises(pilot.PlanError, match="never appended"):
        run(pilot.execute_group(m, samples, _factory({}), tmp_path / "T" / "records.jsonl", prices=DEFAULT_PRICES))


# 8, 9
def test_budget_is_checked_before_any_provider_call(synthetic, tmp_path):
    with pytest.raises(pilot.PlanError, match="exceeds the approved"):
        _frozen(tmp_path, [("metatool_s1", 10)], limit_usd=1e-9)
    plan = pilot.plan_group("U", [("metatool_s1", 3)], seed=5, stratify=True, profile=DETERMINISTIC_V1,
                            jev_repetitions=10, prices=DEFAULT_PRICES)
    with pytest.raises(pilot.PlanError, match="No budget cap"):
        pilot.freeze(plan, tmp_path / "U", allow_dirty=True)
    m = _frozen(tmp_path, [("metatool_s1", 3)])
    over = json.loads(json.dumps(m))
    over["budget_cap_usd"] = 11.0
    over["manifest_hash"] = pilot.manifest_hash(over)
    with pytest.raises(pilot.PlanError, match="not within"):
        pilot.verify_manifest(over, check_git=False)
    under = json.loads(json.dumps(m))
    under["budget_cap_usd"] = under["estimate_usd"] / 2
    log = {}
    from rlcdselect.core.types import FatalRunError
    with pytest.raises(FatalRunError, match="exceeds the cap"):
        run(pilot.execute_group(under, pilot.verify_manifest(m, check_git=False), _factory(log),
                                tmp_path / "U" / "records.jsonl", prices=DEFAULT_PRICES))
    assert "jev" not in log and "llm" in log and log["llm"].requests == []  # nothing was called
    assert m["budget_cap_usd"] == pytest.approx(m["estimate_usd"] * 1.5, rel=1e-3)
    assert m["estimate_usd"] <= m["budget_cap_usd"] <= 10


def test_paired_analysis_requires_exact_alignment():
    def rec(tid, ok, label="x"):
        return {"task_id": tid, "selection_correct": ok, "selection_label": label}
    native = [rec("a", True), rec("b", False), rec("c", True)]
    matched = [rec("a", True), rec("b", True, "y"), rec("c", False, "z")]
    p = paired_native_matched(native, matched)
    assert p["counts"] == {"both_correct": 1, "native_only": 1, "matched_only": 1, "both_wrong": 0}
    assert p["task_ids"]["native_only"] == ["c"] and p["selection_disagreement"]["k"] == 2
    with pytest.raises(ValueError):
        paired_native_matched(native, matched[:2])
    with pytest.raises(ValueError):
        paired_native_matched(native, [rec("a", True), rec("b", True), rec("d", True)])


def test_wilson_and_mcnemar():
    w = wilson(8, 10)
    assert w["rate"] == 0.8 and w["ci95"][0] == pytest.approx(0.4902, abs=1e-3) and w["ci95"][1] == pytest.approx(0.9433, abs=1e-3)
    assert wilson(0, 0)["rate"] is None
    assert mcnemar_exact(0, 0) is None and mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 6) == pytest.approx(2 / 64)


def test_git_state_ignores_results_but_not_code(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (["git", "init", "-q"], ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                                          "--allow-empty", "-m", "x"]):
        subprocess.run(cmd, cwd=repo, check=True)
    assert pilot.git_state(repo)["dirty"] is False
    (repo / "results" / "external_pilot").mkdir(parents=True)
    (repo / "results" / "external_pilot" / "manifest.json").write_text("{}")
    assert pilot.git_state(repo)["dirty"] is False
    (repo / "new_module.py").write_text("x = 1")
    assert pilot.git_state(repo)["dirty"] is True


def test_a_short_stratum_is_an_error_not_a_smaller_sample(synthetic, monkeypatch):
    short = when2call.adapt(w2c_rows(groups=40))  # 40 per label, 50 requested
    monkeypatch.setattr(registry, "_load", lambda src: short)
    with pytest.raises(SamplingError, match="has 40 eligible items, 50 requested"):
        sample_dataset("when2call", 150, seed=7)
