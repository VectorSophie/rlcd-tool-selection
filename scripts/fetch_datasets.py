"""Fetch the pinned upstream benchmark files into the git-ignored `data/external/`.

Network access happens only here. Files come from each dataset's documented GitHub repository at
a pinned commit and are never committed or redistributed by this project.

    uv run --extra laya python scripts/fetch_datasets.py            # everything
    uv run --extra laya python scripts/fetch_datasets.py --only bfcl
"""

import argparse
import json

from rlcdselect.datasets.external.common import SOURCES, fetch

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["when2call", "metatool", "bfcl"], default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = {}
    for key, src in SOURCES.items():
        if args.only and src.dataset != args.only:
            continue
        path, digest = fetch(src, force=args.force)
        manifest[key] = {"url": src.url, "path": str(path), "sha256": digest, "license": src.license}
        print(f"{key:36} {digest[:16]}  {path}")
    print(json.dumps({"fetched": len(manifest)}))
