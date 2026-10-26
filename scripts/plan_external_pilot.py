"""Plan the external benchmark pilot: sample, estimate and freeze one manifest per run group.

No model is called. The only network access is OpenRouter's free endpoint listing, for prices.
The approval rule is applied across all groups at once: the total estimate must not exceed the
approved limit (default $10), and each group's cap is its estimate x 1.5, scaled down if needed so
that the caps together stay within the limit. Over the limit, nothing is frozen and the cost
breakdown is printed; samples are never reduced silently.

    uv run --extra laya python scripts/plan_external_pilot.py --out results/external_pilot
    # then, per group:
    uv run --extra laya python scripts/run_experiment.py --manifest results/external_pilot/A/manifest.json
"""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from rlcdselect.datasets.external.registry import diagnostic_items
from rlcdselect.eval.budget import prices_from_catalog
from rlcdselect.eval.pilot import (
    DEFAULT_APPROVED_LIMIT_USD,
    PlanError,
    allocate_caps,
    estimate_report,
    freeze,
    plan_group,
)
from rlcdselect.llm.openrouter import OpenRouterCatalog
from rlcdselect.profiles import DETERMINISTIC_V1, PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.startup import load_dotenv, require_env, verify_live_models

# The approved first external pilot (2026-10-26): 750 tasks, 1 ordering per task, 3 core arms.
PILOT_GROUPS = {
    "A": [("when2call", 150), ("metatool_s1", 100), ("metatool_s3", 100)],
    "B": [("bfcl_simple_python", 100), ("bfcl_irrelevance", 100)],
    "C": [("bfcl_live_simple", 100), ("bfcl_live_irrelevance", 100)],
}


async def main(args: argparse.Namespace) -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    require_env(["OPENROUTER_API_KEY"])
    catalog = OpenRouterCatalog()
    try:
        verified = await verify_live_models(DETERMINISTIC_V1.llm, JevSelector(), catalog)
    finally:
        await catalog.aclose()
    prices = prices_from_catalog(verified["llm"], verified.get("jev"))
    plans = [plan_group(g, ds, seed=args.seed, stratify=True, profile=DETERMINISTIC_V1,
                        jev_repetitions=PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS, prices=prices)
             for g, ds in PILOT_GROUPS.items()]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        allocate_caps(plans, limit_usd=args.limit_usd)
    except PlanError as exc:
        (out / "estimate.md").write_text(estimate_report(plans) + "\n" + str(exc) + "\n", encoding="utf-8")
        raise SystemExit(str(exc))
    for p in plans:
        path = freeze(p, out / p["group"])
        (out / p["group"] / "estimate.md").write_text(estimate_report([p]), encoding="utf-8")
        print(f"group {p['group']}: estimate ${p['estimate_usd']:.4f}, cap ${p['budget_cap_usd']:.4f}, "
              f"manifest {path} hash {json.loads(path.read_text())['manifest_hash'][:16]}")
    (out / "estimate.md").write_text(estimate_report(plans), encoding="utf-8")
    # Diagnostic BFCL subsets (excluded from primary results): full items stay local, ids and
    # reasons are committed.
    items = diagnostic_items()
    with (out / "diagnostics_bfcl.jsonl").open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    counts = Counter(r for item in items for r in item["exclusion_reasons"])
    (out / "diagnostics_summary.json").write_text(json.dumps({
        "note": "BFCL items excluded from primary results; full gold and schemas in the local diagnostics_bfcl.jsonl",
        "items": len(items), "by_reason": dict(sorted(counts.items())),
        "ids": [{"task_id": i["task_id"], "split": i["source_split"], "reasons": i["exclusion_reasons"]} for i in items],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Diagnostic BFCL items: {len(items)} {dict(counts)}")
    print(estimate_report(plans))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/external_pilot")
    parser.add_argument("--seed", type=int, default=20261026)
    parser.add_argument("--limit-usd", type=float, default=DEFAULT_APPROVED_LIMIT_USD)
    asyncio.run(main(parser.parse_args()))
