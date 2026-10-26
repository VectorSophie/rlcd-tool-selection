"""Analysis of external-pilot records: per dataset × arm metrics with Wilson intervals, paired
native-vs-matched comparison (exact McNemar), Jev selector stability, grounding counts, and cost by
dataset, arm and stage.

This is pilot analysis. Intervals and tests are reported as descriptive uncertainty, not as
confirmatory evidence. When2Call rows from one upstream item (`source_group_id`) are not
independent; their cluster counts are reported and the per-row intervals should be read as
optimistic for that dataset.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from rlcdselect.core.types import ABSTAIN

ARMS = ("native_llm", "matched_llm", "jev")


def wilson(k: int, n: int, z: float = 1.959964) -> dict[str, Any]:
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "ci95": None}
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": p, "ci95": [max(0.0, centre - half), min(1.0, centre + half)]}


def mcnemar_exact(b: int, c: int) -> float | None:
    """Two-sided exact McNemar p-value from the discordant counts (binomial, p = 0.5)."""
    n = b + c
    if n == 0:
        return None
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _label(r: Mapping[str, Any]) -> str:
    return str((r.get("task_provenance") or {}).get("source_label"))


def arm_metrics(rs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    act = [r for r in rs if not r["abstention_expected"]]
    selected = [r for r in rs if r["selection_status"] == "selected"]
    executed = [r for r in rs if r.get("execution_success") is not None]
    by_label = defaultdict(list)
    for r in rs:
        by_label[_label(r)].append(r)

    def count(pred, pool):
        return sum(1 for r in pool if pred(r))

    out = {
        "n": len(rs),
        "selection_accuracy": wilson(count(lambda r: r["selection_correct"], rs), len(rs)),
        "action_selection_accuracy": wilson(count(lambda r: r["selection_correct"], act), len(act)),
        "task_success": wilson(count(lambda r: r["task_success"], rs), len(rs)),
        "grounded_task_success": wilson(count(lambda r: r["grounded_task_success"], rs), len(rs)),
        "abstention_rate": wilson(count(lambda r: r["selection_label"] == ABSTAIN, rs), len(rs)),
        "by_source_label": {
            label: {"n": len(pool),
                    "abstained": wilson(count(lambda r: r["selection_label"] == ABSTAIN, pool), len(pool)),
                    "correct": wilson(count(lambda r: r["selection_correct"], pool), len(pool))}
            for label, pool in sorted(by_label.items())},
        "selector_error_rate": wilson(count(lambda r: r["selector_error"], rs), len(rs)),
        "argument_error_rate": wilson(count(lambda r: r["argument_error"], selected), len(selected)),
        "execution_error_rate": wilson(count(lambda r: r["execution_success"] is False, executed), len(executed)),
        "attacker_or_wrong_tool_rate": wilson(count(lambda r: r["selection_label"] not in (ABSTAIN, None)
                                                    and not r["selection_correct"], rs), len(rs)),
        "arguments_match": wilson(count(lambda r: r.get("arguments_match") is True, rs),
                                  count(lambda r: r.get("arguments_match") is not None, rs)),
        "grounding": {k: sum(r.get(k) or 0 for r in rs) for k in (
            "placeholder_argument_count", "unsupported_required_argument_count",
            "unsupported_optional_argument_count", "unknown_argument_count")},
        "error_kinds": dict(Counter(e["kind"] for r in rs for e in (r.get("errors") or [])).most_common()),
    }
    return out


def paired_native_matched(native: Sequence[Mapping[str, Any]], matched: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Paired by task id (one ordering per task). Raises if the task sets differ."""
    n_by = {r["task_id"]: r for r in native}
    m_by = {r["task_id"]: r for r in matched}
    if set(n_by) != set(m_by) or len(n_by) != len(native) or len(m_by) != len(matched):
        raise ValueError("Native and matched records do not pair one-to-one by task id")
    cells: dict[str, list[str]] = {"both_correct": [], "native_only": [], "matched_only": [], "both_wrong": []}
    disagree = []
    for tid in sorted(n_by):
        a, b = n_by[tid]["selection_correct"], m_by[tid]["selection_correct"]
        key = "both_correct" if a and b else "native_only" if a else "matched_only" if b else "both_wrong"
        cells[key].append(tid)
        if n_by[tid]["selection_label"] != m_by[tid]["selection_label"]:
            disagree.append({"task_id": tid, "native": n_by[tid]["selection_label"],
                             "matched": m_by[tid]["selection_label"]})
    n = len(n_by)
    return {
        "n_pairs": n,
        "counts": {k: len(v) for k, v in cells.items()},
        "task_ids": cells,
        "selection_disagreement": wilson(len(disagree), n),
        "disagreements": disagree,
        "mcnemar_exact_p": mcnemar_exact(len(cells["native_only"]), len(cells["matched_only"])),
    }


def jev_stability(rs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [r for r in rs if r.get("selector_sample_summary")]
    if not rows:
        return {"n_tasks": 0}
    flips, entropies, ranges, stds, unstable = [], [], [], [], []
    executed_agrees_majority = 0
    for r in rows:
        s = r["selector_sample_summary"]
        flips.append(s["choice_flip_rate"])
        entropies.append(s["entropy_bits"])
        per_tool = ((s.get("native_probability_stats") or {}).get("per_tool") or {})
        ranges.append(max((v["range"] for v in per_tool.values()), default=0.0))
        stds.append(max((v["std"] for v in per_tool.values()), default=0.0))
        if s["choice_flip_rate"] > 0:
            unstable.append({"task_id": r["task_id"], "frequencies": s["empirical_choice_frequency"],
                             "executed": r["selection_label"], "majority": s["majority_label"]})
        executed_agrees_majority += r["selection_label"] == s["majority_label"]
    n = len(rows)
    return {
        "n_tasks": n,
        "draws_per_task": sorted({r["selector_sample_summary"]["n_samples"] for r in rows}),
        "tasks_with_any_flip": wilson(len(unstable), n),
        "mean_flip_rate": sum(flips) / n,
        "mean_entropy_bits": sum(entropies) / n,
        "max_entropy_bits": max(entropies),
        "mean_max_probability_range": sum(ranges) / n,
        "max_probability_range": max(ranges),
        "mean_max_probability_std": sum(stds) / n,
        "executed_choice_equals_majority": wilson(executed_agrees_majority, n),
        "unstable_tasks": unstable,
        "note": "Jev native probabilities and empirical choice frequencies are different quantities; "
                "neither is compared numerically with Claude outputs.",
    }


def _metas(meta: Any) -> list[Mapping[str, Any]]:
    if not meta:
        return []
    return list(meta["calls"]) if "calls" in meta else [meta]


def cost_breakdown(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Reported cost per dataset / arm / stage, each provider call counted once (by generation id)."""
    by = defaultdict(lambda: {"selection": 0.0, "arguments": 0.0})
    calls: dict[str, set] = defaultdict(set)
    seen = set()
    for r in records:
        if r.get("record_type", "run") != "run":
            continue
        key = (r.get("dataset"), r["pipeline"])
        sel = _metas(r.get("selection_provider_meta")) + [m for s in (r.get("selector_samples") or [])
                                                          for m in _metas(s.get("provider_meta"))]
        for stage, metas in (("selection", sel), ("arguments", _metas(r.get("argument_provider_meta")))):
            for m in metas:
                gid = m.get("generation_id")
                if gid in seen:
                    continue
                seen.add(gid)
                by[key][stage] += m.get("cost") or 0.0
                calls[m.get("returned_model") or "?"].add(gid)
    datasets = defaultdict(float)
    arms = defaultdict(float)
    stages = defaultdict(float)
    table = []
    for (ds, arm), s in sorted(by.items()):
        table.append({"dataset": ds, "arm": arm, **s, "total": s["selection"] + s["arguments"]})
        datasets[ds] += s["selection"] + s["arguments"]
        arms[arm] += s["selection"] + s["arguments"]
        for k, v in s.items():
            stages[k] += v
    return {"table": table, "by_dataset": dict(datasets), "by_arm": dict(arms), "by_stage": dict(stages),
            "total_usd": sum(datasets.values()), "provider_calls": {k: len(v) for k, v in calls.items()}}


def analyze(records: Sequence[Mapping[str, Any]], manifests: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    runs = [r for r in records if r.get("record_type", "run") == "run"]
    aborted = [r for r in records if r.get("record_type") == "run_aborted"]
    by_ds = defaultdict(list)
    for r in runs:
        by_ds[r["dataset"]].append(r)
    entries = {d["dataset"]: (m, d) for m in manifests for d in m["datasets"]}
    datasets = {}
    for ds, rs in sorted(by_ds.items()):
        m, d = entries.get(ds, ({}, {}))
        arm_rs = {a: [r for r in rs if r["pipeline"] == a] for a in ARMS}
        clusters = {(r.get("task_provenance") or {}).get("source_group_id") for r in arm_rs["native_llm"]} - {None}
        datasets[ds] = {
            "role": d.get("role"), "condition": d.get("condition"), "source_rows": d.get("source_rows"),
            "eligible": d.get("eligible"), "sampled": d.get("sample_size"),
            "not_eligible_by_reason": d.get("not_eligible_by_reason"),
            "clusters_in_sample": len(clusters) or None,
            "arms": {a: arm_metrics(v) for a, v in arm_rs.items() if v},
            "native_vs_matched": (paired_native_matched(arm_rs["native_llm"], arm_rs["matched_llm"])
                                  if arm_rs["native_llm"] and arm_rs["matched_llm"] else None),
            "jev_stability": jev_stability(arm_rs["jev"]),
        }
    return {
        "manifests": [{"group": m["group"], "manifest_hash": m["manifest_hash"], "git_commit": m["git_commit"],
                       "estimate_usd": m["estimate_usd"], "budget_cap_usd": m["budget_cap_usd"]} for m in manifests],
        "records": len(records), "runs": len(runs), "aborted": len(aborted),
        "abort_details": [{k: a.get(k) for k in ("dataset", "task_id", "pipeline", "error_kind", "message")}
                          for a in aborted],
        "manifest_hashes_in_records": sorted({r.get("manifest_hash") for r in records}),
        "datasets": datasets,
        "cost": cost_breakdown(records),
        "estimate_usd": sum(m["estimate_usd"] for m in manifests),
    }


def _pct(w: Mapping[str, Any] | None) -> str:
    if not w or w.get("rate") is None:
        return "–"
    lo, hi = w["ci95"]
    return f"{w['rate']:.0%} [{lo:.0%}, {hi:.0%}] (n={w['n']})"


def markdown(summary: Mapping[str, Any]) -> str:
    c = summary["cost"]
    ratio = c["total_usd"] / summary["estimate_usd"] if summary["estimate_usd"] else float("nan")
    lines = [
        "# External benchmark pilot: summary", "",
        "Pilot observations only. Rates show Wilson 95% intervals. When2Call rows from one upstream item are "
        "correlated (clusters reported), so its intervals are optimistic. MetaTool runs under the name + description "
        "condition (no source schemas) and is not pooled with schema-bearing datasets. BFCL `live_relevance` "
        "(sanity only) and the BFCL diagnostic subsets are not part of these results.", "",
        f"- Records: {summary['records']} ({summary['runs']} runs, {summary['aborted']} aborted)",
        f"- Provider calls: {c['provider_calls']}",
        f"- Cost: ${c['total_usd']:.4f} actual vs ${summary['estimate_usd']:.4f} estimated (ratio {ratio:.2f})",
        f"- Manifests: " + ", ".join(f"{m['group']} `{m['manifest_hash'][:12]}`" for m in summary["manifests"]), "",
        "## Results by dataset and arm", "",
        "| dataset | arm | selection accuracy | task success | grounded task success | abstained | selector err | arg err | exec err |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for ds, d in summary["datasets"].items():
        for arm, m in d["arms"].items():
            lines.append(f"| {ds} | {arm} | {_pct(m['selection_accuracy'])} | {_pct(m['task_success'])} | "
                         f"{_pct(m['grounded_task_success'])} | {_pct(m['abstention_rate'])} | "
                         f"{_pct(m['selector_error_rate'])} | {_pct(m['argument_error_rate'])} | {_pct(m['execution_error_rate'])} |")
    lines += ["", "## Abstention by original label", "",
              "| dataset | arm | label | n | abstained | correct |", "|---|---|---|---|---|---|"]
    for ds, d in summary["datasets"].items():
        for arm, m in d["arms"].items():
            for label, v in m["by_source_label"].items():
                lines.append(f"| {ds} | {arm} | {label} | {v['n']} | {_pct(v['abstained'])} | {_pct(v['correct'])} |")
    lines += ["", "## Native vs matched (same Claude model; paired by task)", "",
              "| dataset | pairs | both correct | native only | matched only | both wrong | disagreement | McNemar exact p |",
              "|---|---|---|---|---|---|---|---|"]
    for ds, d in summary["datasets"].items():
        p = d["native_vs_matched"]
        if p:
            k = p["counts"]
            pv = "–" if p["mcnemar_exact_p"] is None else f"{p['mcnemar_exact_p']:.3g}"
            lines.append(f"| {ds} | {p['n_pairs']} | {k['both_correct']} | {k['native_only']} | {k['matched_only']} | "
                         f"{k['both_wrong']} | {_pct(p['selection_disagreement'])} | {pv} |")
    lines += ["", "## Jev selector stability (10 back-to-back draws per task)", "",
              "| dataset | tasks | tasks with any flip | mean flip rate | mean entropy (bits) | mean max prob. range | max prob. range | executed = majority |",
              "|---|---|---|---|---|---|---|---|"]
    for ds, d in summary["datasets"].items():
        j = d["jev_stability"]
        if j.get("n_tasks"):
            lines.append(f"| {ds} | {j['n_tasks']} | {_pct(j['tasks_with_any_flip'])} | {j['mean_flip_rate']:.3f} | "
                         f"{j['mean_entropy_bits']:.3f} | {j['mean_max_probability_range']:.3f} | "
                         f"{j['max_probability_range']:.3f} | {_pct(j['executed_choice_equals_majority'])} |")
    lines += ["", "## Grounding (argument values)", "",
              "| dataset | arm | placeholders | unsupported required | unsupported optional | unknown |", "|---|---|---|---|---|---|"]
    for ds, d in summary["datasets"].items():
        for arm, m in d["arms"].items():
            g = m["grounding"]
            lines.append(f"| {ds} | {arm} | {g['placeholder_argument_count']} | {g['unsupported_required_argument_count']} | "
                         f"{g['unsupported_optional_argument_count']} | {g['unknown_argument_count']} |")
    lines += ["", "## Cost (reported by OpenRouter)", "", "| dataset | arm | selection $ | arguments $ | total $ |",
              "|---|---|---|---|---|"]
    for row in c["table"]:
        lines.append(f"| {row['dataset']} | {row['arm']} | {row['selection']:.4f} | {row['arguments']:.4f} | {row['total']:.4f} |")
    lines += ["", f"By arm: " + ", ".join(f"{k} ${v:.4f}" for k, v in c["by_arm"].items()),
              f"By stage: " + ", ".join(f"{k} ${v:.4f}" for k, v in c["by_stage"].items())]
    return "\n".join(lines) + "\n"
