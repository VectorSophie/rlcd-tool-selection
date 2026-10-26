"""Recompute grounding-aware scoring and selector stability for existing run records. Offline.

Records are read, never modified. Older records have no evaluator grounding rules or evaluation
context, so the current fixture's (if any) are applied by task id. Prints, per file and arm: the
original `task_success`, grounded task success under the strict earlier policy
(`strict_old_grounding`: any unsupported value fails) and under the refined default
(`refined_grounding`: only placeholders and unsupported required/critical values fail), the tasks
that change, provenance counts, and pooled selector stability for the requested arm.

    uv run --extra laya python scripts/rescore_pilot.py results/live/*.jsonl
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from rlcdselect.datasets.fixtures import load_fixtures
from rlcdselect.eval.grounding import ground_record, status_counts
from rlcdselect.eval.logging import read_jsonl
from rlcdselect.eval.stability import selector_stability

ARMS = ("native_llm", "matched_llm", "jev")


def main(paths: list[str], stability_arm: str) -> None:
    fixture_tasks = {t.task_id: t for t in load_fixtures()[1]}
    pooled = []
    totals = Counter()
    for path in paths:
        records = [r for r in read_jsonl(path) if r.get("record_type", "run") == "run"]
        pooled += records
        print(f"\n## {Path(path).name}  ({len(records)} runs)")
        print(f"{'arm':12} {'task_success':>13} {'strict_old':>13} {'refined':>13}  strict->refined changes (task: count)")
        by_arm = defaultdict(list)
        for r in records:
            t = fixture_tasks.get(r["task_id"])
            by_arm[r["pipeline"]].append((r, ground_record(r, t.argument_grounding if t else None,
                                                           t.evaluation_context if t else None)))
        for arm in [a for a in ARMS if a in by_arm] + [a for a in by_arm if a not in ARMS]:
            rows = by_arm[arm]
            n = len(rows)
            old = sum(bool(r["task_success"]) for r, _ in rows)
            strict = sum(bool(g["grounded_task_success_strict"]) for _, g in rows)
            refined = sum(bool(g["grounded_task_success"]) for _, g in rows)
            changed = Counter(r["task_id"] for r, g in rows
                              if bool(g["grounded_task_success_strict"]) != bool(g["grounded_task_success"]))
            totals["records"] += n
            totals["strict_vs_original"] += sum(bool(r["task_success"]) != bool(g["grounded_task_success_strict"]) for r, g in rows)
            totals["refined_vs_original"] += sum(bool(r["task_success"]) != bool(g["grounded_task_success"]) for r, g in rows)
            totals["refined_vs_strict"] += sum(changed.values())
            for _, g in rows:
                for k in ("placeholder_argument_count", "unsupported_required_argument_count",
                          "unsupported_optional_argument_count", "unknown_argument_count"):
                    totals[k] += g[k] or 0
            print(f"{arm:12} {old:>5}/{n:<7} {strict:>5}/{n:<7} {refined:>5}/{n:<7}  {dict(changed)}")
            counts = status_counts(g["argument_provenance"] for _, g in rows)
            print(f"{'':12} provenance: { {k: v for k, v in counts.items() if v} }")

    print("\n## Totals")
    print(json.dumps(dict(totals), indent=2))

    print(f"\n## Selector stability, {stability_arm}, pooled per (profile, condition, task, ordering)")
    arm_records = [r for r in pooled if r["pipeline"] == stability_arm]
    stab = selector_stability(arm_records)
    print(f"{'profile':18} {'condition':32} {'task':30} {'order':>5} {'n':>3} {'flip':>5}  frequencies")
    for (_, _, profile, condition, task, order, _), s in sorted(stab.items(), key=lambda kv: tuple(map(str, kv[0]))):
        if s["n_samples"] < 2 or s["choice_flip_rate"] == 0:
            continue
        freq = {k: round(v, 2) for k, v in s["empirical_choice_frequency"].items()}
        print(f"{profile:18} {condition:32} {task:30} {order!s:>5} {s['n_samples']:>3} {s['choice_flip_rate']:>5.2f}  {freq}")
    ranges = [(k, t, v["range"]) for k, s in stab.items() if s["native_probability_stats"]
              for t, v in s["native_probability_stats"].get("per_tool", {}).items()]
    if ranges:
        k, t, r = max(ranges, key=lambda x: x[2])
        print(f"largest native-probability range across identical requests: {r:.3f} ({t}; task {k[4]}, order {k[5]})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--stability-arm", default="jev")
    args = parser.parse_args()
    main(args.paths, args.stability_arm)
    print(json.dumps({"note": "records unchanged; rules from current fixture applied by task id"}))
