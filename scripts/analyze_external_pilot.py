"""Summarize an external pilot: reads `<dir>/<group>/manifest.json` and `records.jsonl`, writes
`<dir>/summary.json` and `<dir>/SUMMARY.md`. Offline.

    uv run --extra laya python scripts/analyze_external_pilot.py results/external_pilot
"""

import argparse
import json
from pathlib import Path

from rlcdselect.eval.logging import read_jsonl
from rlcdselect.eval.pilot import manifest_hash
from rlcdselect.eval.pilot_analysis import analyze, markdown

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path)
    args = parser.parse_args()
    manifests, records = [], []
    for mpath in sorted(args.dir.glob("*/manifest.json")):
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        if manifest_hash(manifest) != manifest["manifest_hash"]:
            raise SystemExit(f"{mpath}: manifest hash mismatch")
        rpath = mpath.parent / "records.jsonl"
        if not rpath.exists():
            print(f"skipping group {manifest['group']}: no records")
            continue
        recs = read_jsonl(rpath)
        bad = {r.get("manifest_hash") for r in recs} - {manifest["manifest_hash"]}
        if bad:
            raise SystemExit(f"{rpath}: records from another manifest {bad}")
        manifests.append(manifest)
        records += recs
    summary = analyze(records, manifests)
    (args.dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.dir / "SUMMARY.md").write_text(markdown(summary), encoding="utf-8")
    print(markdown(summary))
