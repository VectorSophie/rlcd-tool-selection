"""Adapters that convert external benchmarks into project `Task`s (Phase 4).

Source files are read from local copies fetched from their pinned upstream commits
(`scripts/fetch_datasets.py`, into the git-ignored `data/external/`). Nothing is redistributed.
Every included task carries evaluator-only `provenance`; every skipped row becomes an `Exclusion`
with a reason, so inclusion is reproducible and auditable.
"""
