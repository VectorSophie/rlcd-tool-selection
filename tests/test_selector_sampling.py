"""Repeated selector sampling (selector stability) vs end-to-end execution.

The pilot showed Jev returning different probabilities, and sometimes a different choice, for
identical requests. These tests pin down how repeated draws are taken, stored and summarized.
"""

from pathlib import Path

import pytest
from conftest import run
from helpers import call, response

from rlcdselect.core.serialization import ABSTAIN_ID, present_task
from rlcdselect.core.types import ABSTAIN, ProbabilityKind, SelectorSamplingPolicy, Usage
from rlcdselect.eval.budget import DEFAULT_PRICES, BudgetGuard, estimate_run_cost
from rlcdselect.eval.logging import JsonlWriter, read_jsonl
from rlcdselect.eval.metrics import selector_stability, summarize
from rlcdselect.eval.replay import task_from_record
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import ScriptedChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.selectors.base import SelectorOutput
from rlcdselect.selectors.mock import ScriptedSelector

TASK = "similar_send_not_draft"  # candidates: create_email_draft, send_email, calendar_lookup
ARGS = {"to": ["alice@example.com"], "subject": "Lunch", "body": "I am running ten minutes late."}
EXAMPLES = Path(__file__).resolve().parent.parent / "results" / "examples"


def ids(task, serialization):
    cset = present_task(task, serialization, order_seed=None, id_seed=None)
    return {c.tool.key: c.candidate_id for c in cset.candidates}


def draw(choice, probabilities, cost=None):
    meta = {"generation_id": f"gen-{choice}-{sum(probabilities.values()):.3f}-{id(probabilities)}", "cost": cost}
    return SelectorOutput(choice, probabilities, None, Usage(300, 0), "jev-test", raw={"draw": choice},
                          provider_meta=meta)


def jev_like(steps):
    return ScriptedSelector(steps, selector_id="jev", probability_kind=ProbabilityKind.RLCD_NATIVE)


def arg_reply(task, serialization):
    send = next(c for c in present_task(task, serialization, order_seed=None, id_seed=None).candidates
                if c.tool.key == "mail/send_email")
    return response(call(send.display_name, ARGS))


def draws_send_abstain(i):
    """6 x send_email, 4 x abstain, with probabilities that move between identical calls."""
    send, draft = i["mail/send_email"], i["mail/create_email_draft"]
    return ([draw(send, {send: 0.59 + k / 100, draft: 0.05, i["calendar/calendar_lookup"]: 0.0, ABSTAIN_ID: 0.36 - k / 100})
             for k in range(6)]
            + [draw(ABSTAIN_ID, {send: 0.45, draft: 0.04, i["calendar/calendar_lookup"]: 0.0, ABSTAIN_ID: 0.51})
               for _ in range(4)])


def experiment(task, serialization, steps, policy, arg_replies, tmp_path, budget=None):
    selector = jev_like(steps)
    llm = ScriptedChatClient(arg_replies)
    executor = MockExecutor()
    pipeline = DecomposedPipeline(selector, ArgumentGenerator(llm), executor, serialization, sampling=policy)
    path = tmp_path / "r.jsonl"
    records = run(run_experiment([task], [pipeline], ExperimentConfig("s", profile="p", condition="c"),
                                 JsonlWriter(path, secrets=()), budget=budget))
    return records, selector, llm, executor, read_jsonl(path)


def test_identical_requests_can_yield_different_choices(tasks, serialization, tmp_path):  # 1
    task = tasks[TASK]
    i = ids(task, serialization)
    records, selector, _, _, _ = experiment(task, serialization, draws_send_abstain(i),
                                            SelectorSamplingPolicy(repetitions=10), [arg_reply(task, serialization)],
                                            tmp_path)
    assert len(selector.requests) == 10 and all(r == selector.requests[0] for r in selector.requests)
    labels = [s["selection_label"] for s in records[0]["selector_samples"]]
    assert set(labels) == {"mail/send_email", ABSTAIN}


def test_every_sample_is_preserved_and_frequencies_sum_to_one(tasks, serialization, tmp_path):  # 2, 3
    task = tasks[TASK]
    i = ids(task, serialization)
    steps = draws_send_abstain(i)
    records, _, _, _, lines = experiment(task, serialization, steps, SelectorSamplingPolicy(repetitions=10),
                                         [arg_reply(task, serialization)], tmp_path)
    (rec,) = lines
    samples = rec["selector_samples"]
    assert [s["sample_index"] for s in samples] == list(range(10))
    assert [s["raw"] for s in samples] == [s.raw for s in steps]
    assert [s["probabilities"] for s in samples] == [s.probabilities for s in steps]  # by candidate id, as returned
    assert samples[0]["probabilities_by_tool"]["mail/send_email"] == pytest.approx(0.59)
    summary = rec["selector_sample_summary"]
    assert sum(summary["empirical_choice_frequency"].values()) == pytest.approx(1.0)
    assert summary["empirical_choice_frequency"] == {ABSTAIN: 0.4, "mail/send_email": 0.6}
    assert (summary["trusted_frequency"], summary["abstention_frequency"], summary["attacker_frequency"]) == (0.6, 0.4, 0.0)
    assert summary["choice_flip_rate"] == pytest.approx(1 - (6 * 5 + 4 * 3) / 90)
    assert summary["entropy_bits"] == pytest.approx(0.97095, abs=1e-4)
    stats = summary["native_probability_stats"]
    assert stats["probability_kind"] == "rlcd_native"
    assert stats["per_tool"]["mail/send_email"]["range"] == pytest.approx(0.64 - 0.45)


def test_majority_vote_is_derived_and_never_replaces_the_samples(tasks, serialization, tmp_path):  # 4
    task = tasks[TASK]
    i = ids(task, serialization)
    steps = list(reversed(draws_send_abstain(i)))  # first draw abstains; the majority is send_email
    records, _, llm, _, _ = experiment(task, serialization, steps, SelectorSamplingPolicy(repetitions=10), [], tmp_path)
    (rec,) = records
    assert rec["selector_sample_summary"]["majority_label"] == "mail/send_email"
    assert rec["selection_label"] == ABSTAIN  # the run's selection is draw 0, not the majority
    assert len(rec["selector_samples"]) == 10
    assert llm.requests == []  # draw 0 abstained, so nothing was generated

    tie = summarize_two_way_tie(i)
    assert tie["majority_label"] is None


def summarize_two_way_tie(i):
    from rlcdselect.eval.stability import summarize_samples
    return summarize_samples([{"selection_label": "a"}, {"selection_label": "b"}])


def test_selector_only_repetition_runs_arguments_and_execution_once(tasks, serialization, tmp_path):  # 5
    task = tasks[TASK]
    i = ids(task, serialization)
    records, selector, llm, executor, lines = experiment(task, serialization, draws_send_abstain(i),
                                                         SelectorSamplingPolicy(repetitions=10),
                                                         [arg_reply(task, serialization)], tmp_path)
    assert len(selector.requests) == 10
    assert len(llm.requests) == 1 and len(executor.calls) == 1
    assert [line["record_type"] for line in lines] == ["run"]
    assert lines[0]["selector_sampling"] == {"repetitions": 10, "execute_each_sample": False,
                                             "execution_sample_index": 0}
    assert lines[0]["execution_sample_index"] == 0
    assert [smp["used_for_execution"] for smp in lines[0]["selector_samples"]] == [True] + [False] * 9


def test_end_to_end_repetition_only_when_requested(tasks, serialization, tmp_path):  # 6
    task = tasks[TASK]
    i = ids(task, serialization)
    replies = [arg_reply(task, serialization) for _ in range(6)]  # one per draw that selected send_email
    records, _, llm, executor, lines = experiment(
        task, serialization, draws_send_abstain(i),
        SelectorSamplingPolicy(repetitions=10, execute_each_sample=True), replies, tmp_path)
    assert len(llm.requests) == 6 and len(executor.calls) == 6
    types = [line["record_type"] for line in lines]
    assert types == ["run"] + ["selector_sample_run"] * 9
    children = lines[1:]
    assert [c["selector_sample_index"] for c in children] == list(range(1, 10))
    assert {c["parent_run_id"] for c in children} == {lines[0]["run_id"]}
    assert [c["selection_label"] for c in children] == ["mail/send_email"] * 5 + [ABSTAIN] * 4
    # Primary cross-arm metrics count the run once, not once per draw.
    assert summarize(lines)["jev"]["n"] == 1
    with pytest.raises(ValueError):
        SelectorSamplingPolicy(repetitions=1, execute_each_sample=True)


def test_probability_variation_is_recorded_without_renormalization(tasks, serialization, tmp_path):  # 7
    task = tasks[TASK]
    i = ids(task, serialization)
    send, draft, cal = i["mail/send_email"], i["mail/create_email_draft"], i["calendar/calendar_lookup"]
    steps = [draw(send, {send: 0.6, draft: 0.1, cal: 0.0, ABSTAIN_ID: 0.3}),
             draw(send, {send: 0.5, draft: 0.1, cal: 0.0, ABSTAIN_ID: 0.2}),  # sums to 0.8
             draw(send, {send: 0.7, draft: 0.0, cal: 0.0, ABSTAIN_ID: 0.3})]
    records, *_ = experiment(task, serialization, steps, SelectorSamplingPolicy(repetitions=3),
                             [arg_reply(task, serialization)], tmp_path)
    samples = records[0]["selector_samples"]
    assert samples[1]["probabilities"] == {send: 0.5, draft: 0.1, cal: 0.0, ABSTAIN_ID: 0.2}  # unchanged
    assert samples[1]["probability_issues"] == ["sum=0.800000"]
    stats = records[0]["selector_sample_summary"]["native_probability_stats"]
    assert stats["n_samples"] == 2 and stats["n_excluded_for_issues"] == 1
    assert stats["per_tool"]["mail/send_email"]["mean"] == pytest.approx(0.65)
    assert stats["per_tool"]["mail/send_email"]["std"] == pytest.approx(0.05)


def test_old_single_sample_record_files_remain_readable():  # 8
    lines = read_jsonl(EXAMPLES / "smoke_offline_v2.jsonl")
    assert lines and "selector_samples" not in lines[0] and lines[0]["schema_version"] == 1
    stability = selector_stability(lines)
    assert stability and all(s["n_samples"] >= 1 for s in stability.values())
    # Pooling repeated old runs of the same request (key without the ordering) counts every run once.
    pooled = selector_stability(lines, key=lambda r: (r["pipeline"], r["task_id"]))
    per_task = {k: v["n_samples"] for k, v in pooled.items()}
    assert set(per_task.values()) == {len({r["order_seed"] for r in lines})}
    assert summarize(lines)
    task_from_record(lines[0])


def test_repeated_draws_are_charged_once_each(tasks, serialization, tmp_path):
    task = tasks[TASK]
    i = ids(task, serialization)
    send = i["mail/send_email"]
    steps = [draw(send, {send: 0.6 + k / 100, ABSTAIN_ID: 0.4 - k / 100}, cost=0.001) for k in range(4)]
    guard = BudgetGuard(cap_usd=1.0)
    replies = [arg_reply(task, serialization) for _ in range(4)]
    records, *_ = experiment(task, serialization, steps, SelectorSamplingPolicy(repetitions=4, execute_each_sample=True),
                             replies, tmp_path, budget=guard)
    # 4 selector draws at 0.001 reported; 4 argument calls by tokens (fake usage 10 in / 5 out).
    arg_cost = 10 * DEFAULT_PRICES.llm_input + 5 * DEFAULT_PRICES.llm_output
    assert records[0]["cost_charged_usd"] == pytest.approx(0.004 + arg_cost)
    assert [r["cost_charged_usd"] for r in records[1:]] == pytest.approx([arg_cost] * 3)  # selection not re-charged
    assert guard.spent_usd == pytest.approx(0.004 + 4 * arg_cost)


def test_estimate_scales_with_selector_repetitions(core, serialization):
    one = estimate_run_cost(core, ["jev"], serialization, DEFAULT_PRICES, 1, 1)
    five = estimate_run_cost(core, ["jev"], serialization, DEFAULT_PRICES, 1, 1,
                             sampling={"jev": SelectorSamplingPolicy(repetitions=5)})
    e2e = estimate_run_cost(core, ["jev"], serialization, DEFAULT_PRICES, 1, 1,
                            sampling={"jev": SelectorSamplingPolicy(repetitions=5, execute_each_sample=True)})
    assert one["total_usd"] < five["total_usd"] < 1.2 * one["total_usd"]  # Jev draws are nearly free
    assert e2e["total_usd"] > 4 * one["total_usd"]  # end-to-end repeats the paid argument calls


def test_execution_sample_is_explicit_and_configurable(tasks, serialization, tmp_path):
    task = tasks[TASK]
    i = ids(task, serialization)
    steps = list(reversed(draws_send_abstain(i)))  # draws 0-3 abstain, 4-9 select send_email
    records, _, llm, _, lines = experiment(task, serialization, steps,
                                           SelectorSamplingPolicy(repetitions=10, execution_sample_index=4),
                                           [arg_reply(task, serialization)], tmp_path)
    (rec,) = lines
    assert rec["execution_sample_index"] == 4 and rec["selection_label"] == "mail/send_email"
    assert [smp["used_for_execution"] for smp in rec["selector_samples"]] == [i == 4 for i in range(10)]
    assert len(llm.requests) == 1
    with pytest.raises(ValueError):
        SelectorSamplingPolicy(repetitions=3, execution_sample_index=3)


def test_children_carry_their_own_execution_sample_index(tasks, serialization, tmp_path):
    task = tasks[TASK]
    i = ids(task, serialization)
    replies = [arg_reply(task, serialization) for _ in range(6)]
    _, _, _, _, lines = experiment(task, serialization, draws_send_abstain(i),
                                   SelectorSamplingPolicy(repetitions=10, execute_each_sample=True), replies, tmp_path)
    assert [line["execution_sample_index"] for line in lines] == list(range(10))
    assert all(line["selector_samples"] is None for line in lines[1:])  # draws live in the parent only


def test_profile_jev_policy_is_the_documented_development_default():
    from rlcdselect.profiles import (DEFAULT_JEV_SELECTOR_REPETITIONS, DETERMINISTIC_V1,
                                     PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS, STOCHASTIC_V1)
    assert (DEFAULT_JEV_SELECTOR_REPETITIONS, PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS) == (5, 10)
    assert DETERMINISTIC_V1.jev_selector_repetitions == 5 and STOCHASTIC_V1.jev_selector_repetitions == 1
    assert DETERMINISTIC_V1.selector_sampling["jev"].execution_sample_index == 0
