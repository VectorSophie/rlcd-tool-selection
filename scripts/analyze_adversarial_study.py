"""Analyse the adversarial study: reads `<dir>/*/manifest.json` and `records.jsonl`, checks every
record carries its group's manifest hash, and writes `summary.json`, `SUMMARY.md` and
`CLEAN_ABLATION.md` (no model calls).

    uv run --extra laya python scripts/analyze_adversarial_study.py results/adversarial_study
"""

import argparse
import json
from pathlib import Path

from rlcdselect.eval.adversarial_analysis import analyze, clean_markdown, markdown
from rlcdselect.eval.logging import read_jsonl


def main(root: Path) -> None:
    manifests, records = [], []
    for path in sorted(root.glob("*/manifest.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        rec_path = path.parent / "records.jsonl"
        if not rec_path.exists():
            print(f"{m['group']}: no records, skipped")
            continue
        rs = read_jsonl(rec_path)
        bad = {r.get("manifest_hash") for r in rs if r.get("record_type") == "run"} - {m["manifest_hash"]}
        if bad:
            raise SystemExit(f"{rec_path}: records from another manifest {sorted(bad)}")
        manifests.append(m)
        records += rs
    summary = analyze(records, manifests)
    (root / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    (root / "SUMMARY.md").write_text(markdown(summary), encoding="utf-8")
    (root / "CLEAN_ABLATION.md").write_text(clean_markdown(summary), encoding="utf-8")
    print(f"Wrote {root / 'summary.json'}, SUMMARY.md and CLEAN_ABLATION.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir")
    main(Path(parser.parse_args().dir))
