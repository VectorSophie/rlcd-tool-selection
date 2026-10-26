"""Adapt the locally fetched benchmarks and print inclusion/exclusion reports. Offline; no model calls.

    uv run --extra laya python scripts/adapt_datasets.py [--json results/adapters/report.json]
"""

import argparse
import json
from pathlib import Path

from rlcdselect.datasets.external import bfcl, metatool, when2call
from rlcdselect.datasets.external.common import BFCL_EXCLUDED_SUBSETS, BFCL_INCLUDED_SUBSETS


def reports() -> list[dict]:
    results = [when2call.load()] + [metatool.load(s) for s in metatool.SUBSETS] + \
              [bfcl.load(s) for s in BFCL_INCLUDED_SUBSETS]
    out = []
    for r in results:
        s = r.summary()
        transformations = {}
        for t in r.tasks:
            for x in t.provenance["transformations"]:
                transformations[x] = transformations.get(x, 0) + 1
        s["tasks_with_transformation"] = dict(sorted(transformations.items()))
        out.append(s)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    rows = reports()
    for s in rows:
        subset = s["source"].get("subset") or s["source"]["file"].split("/")[-1]
        print(f"\n## {s['dataset']} / {subset}: {s['source_rows']} rows -> {s['included']} included, {s['excluded']} excluded")
        print(f"   included by label: {s['included_by_source_label']}")
        print(f"   exclusions: {s['exclusion_reasons']}")
        print(f"   transformations (tasks affected): {s['tasks_with_transformation']}")
    print(f"\nBFCL subsets not adapted: {BFCL_EXCLUDED_SUBSETS}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"reports": rows, "bfcl_excluded_subsets": BFCL_EXCLUDED_SUBSETS}, indent=2))
