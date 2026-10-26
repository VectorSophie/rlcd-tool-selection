# RLCDSelect

A research harness that compares tool-selection architectures under matched conditions:

1. **Native LLM tool calling**: one LLM sees every tool, then selects and fills arguments.
2. **Matched decomposed LLM**: the same LLM picks one tool via a System One-style Choice; the same LLM then fills arguments for that tool only.
3. **RLCD selection**: Jev (`typesafe/jev-1.13`) or Laya (secondary) picks the tool; the same LLM fills arguments.

The shared LLM is Claude Haiku 4.5 through OpenRouter, served by Anthropic only. Jev also goes through OpenRouter, so one `OPENROUTER_API_KEY` covers the pilot.

Primary metrics are discrete selection outcomes. Selector-reported probabilities are analyzed only within one selector. `grounded_task_success` (correct selection, successful execution, and every argument value traceable to the request) is the intended primary end-to-end metric; `task_success` is kept unchanged alongside it.

Jev is not deterministic for identical requests, so decomposed arms can repeat the selector call (`SelectorSamplingPolicy`): selector-only draws for stability measurement by default, end-to-end repetition only when requested. Tools can come from a static fixture registry or from MCP servers through the official MCP Python SDK (`MCPToolRegistry`, `MCPExecutor`).

Status: a 14-task fixture pilot (1,554 runs) has been run. Its results are hypothesis-generating pilot observations, not general findings; see `IMPLEMENTATION_REPORT.md`.

- Design: [`DESIGN.md`](DESIGN.md)
- Status: [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md)
- Prior-work review: [`research/`](research/)

```sh
uv sync --extra laya                      # Laya extra is optional (pulls torch)
uv run --extra laya pytest                # offline tests, including provider payload snapshots
uv run --extra laya python scripts/smoke_offline.py
uv run --extra laya python scripts/rescore_pilot.py results/live/*.jsonl   # offline: grounding + stability from records
uv run --extra laya python -m rlcdselect.datasets.mcp_fixture_server mail  # a local fixture MCP server over stdio
uv run --extra laya python scripts/run_experiment.py \
    --profile deterministic_v1 --condition architecture_matched_v1 --check-only   # needs OPENROUTER_API_KEY; no paid calls
```

License: Apache-2.0.
