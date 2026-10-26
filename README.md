# RLCDSelect

A research harness that compares tool-selection architectures under matched conditions:

1. **Native LLM tool calling**: one LLM sees every tool, then selects and fills arguments.
2. **Matched decomposed LLM**: the same LLM picks one tool via a System One-style Choice; the same LLM then fills arguments for that tool only.
3. **RLCD selection**: Jev (`typesafe/jev-1.13`) or Laya (secondary) picks the tool; the same LLM fills arguments.

The shared LLM is Claude Haiku 4.5 through OpenRouter, served by Anthropic only. Jev also goes through OpenRouter, so one `OPENROUTER_API_KEY` covers the pilot.

Primary metrics are discrete selection outcomes. Selector-reported probabilities are analyzed only within one selector.

`grounded_task_success` is the intended primary end-to-end metric. It requires correct selection, successful execution, and no hard grounding failure; a hard failure is a placeholder, or an unsupported required or critical argument value. Grounding policy `refined_v1` treats an invented *optional* value as a warning. `task_success` and the earlier strict grounding metric are kept alongside it.

Jev is not deterministic for identical requests, so decomposed arms can repeat the selector call (`SelectorSamplingPolicy`). By default these are selector-only draws, for stability measurement. Only the draw at a fixed `execution_sample_index` (the first) goes on to argument generation and execution; end-to-end repetition happens only when requested. The development default is 5 Jev draws; the pilot recommendation is 10; the final N will be chosen from external-dataset variance.

Tools can come from a static fixture registry or from MCP servers through the official MCP Python SDK (`--registry static|mcp`, `--executor mock|mcp`). Adapters for When2Call, MetaTool and BFCL (single-call subsets) convert benchmark rows into tasks with per-item provenance and exclusion reports. Their data is fetched from pinned upstream commits and never committed.

Status: a 14-task fixture pilot (1,554 runs) plus one 126-run regression check have been run. Their results are fixture-level pilot observations and hypotheses, not general findings; see `IMPLEMENTATION_REPORT.md`. No external benchmark has been run yet.

- Design: [`DESIGN.md`](DESIGN.md)
- Status: [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md)
- Prior-work review: [`research/`](research/)

```sh
uv sync --extra laya                      # Laya extra is optional (pulls torch)
uv run --extra laya pytest                # offline tests, including provider payload snapshots
uv run --extra laya python scripts/smoke_offline.py
uv run --extra laya python scripts/rescore_pilot.py results/live/*.jsonl   # offline: grounding + stability from records
uv run --extra laya python scripts/smoke_offline.py --mcp                 # local MCP smoke mode (fixture MCP servers)
uv run --extra laya python -m rlcdselect.datasets.mcp_fixture_server mail  # a local fixture MCP server over stdio
uv run --extra laya python scripts/fetch_datasets.py                       # pinned When2Call / MetaTool / BFCL files -> data/external/
uv run --extra laya python scripts/adapt_datasets.py                       # offline inclusion/exclusion report
uv run --extra laya python scripts/run_experiment.py \
    --profile deterministic_v1 --condition architecture_matched_v1 --check-only   # needs OPENROUTER_API_KEY; no paid calls
```

License: Apache-2.0.
