# RLCDSelect

A research harness that compares tool-selection architectures under matched conditions:

1. **Native LLM tool calling**: one LLM sees every tool, then selects and fills arguments.
2. **Matched decomposed LLM**: the same LLM picks one tool via a System One-style Choice; the same LLM then fills arguments for that tool only.
3. **RLCD selection**: Jev (pinned `jev-1.13.0`) or Laya (secondary) picks the tool; the same LLM fills arguments.

Primary metrics are discrete selection outcomes. Selector-reported probabilities are analyzed only within one selector.

- Design: [`DESIGN.md`](DESIGN.md)
- Status: [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md)
- Prior-work review: [`research/`](research/)

```sh
uv sync --extra laya                      # Laya extra is optional (pulls torch)
uv run --extra laya pytest                # offline tests, including provider payload snapshots
uv run --extra laya python scripts/smoke_offline.py
uv run --extra laya python scripts/run_experiment.py \
    --profile deterministic_v1 --condition architecture_matched_v1 --check-only   # needs API keys
```

License: Apache-2.0.
