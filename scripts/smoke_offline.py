"""Offline end-to-end smoke run over the static fixtures. No network, no API keys.

Arms: native (fake keyword LLM) and decomposed (keyword mock selector + the same fake LLM for
arguments). The fakes' decisions are not a model's; this checks wiring, logging and metrics only.

    uv run python scripts/smoke_offline.py [--out results/smoke]
    uv run python scripts/smoke_offline.py --mcp   # tools listed and executed via the local fixture MCP servers
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rlcdselect.datasets.fixtures import core_tasks, load_fixtures
from rlcdselect.datasets.mcp_fixture_server import fixture_servers
from rlcdselect.execution.mcp_executor import MCPExecutor
from rlcdselect.registry.mcp_registry import MCPToolRegistry
from rlcdselect.registry.sources import rebind_tasks
from rlcdselect.eval.logging import JsonlWriter
from rlcdselect.eval.metrics import selection_frequencies, summarize
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.fake import KeywordChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import ARCHITECTURE_MATCHED_V1
from rlcdselect.selectors.mock import KeywordSelector


async def main(out_dir: Path, mcp: bool = False) -> list[dict]:
    _, tasks = load_fixtures()
    tasks = core_tasks(tasks)  # decomposed-only stress tasks are excluded from cross-arm runs
    if not mcp:
        return await _run(out_dir, tasks, MockExecutor(), {"registry": "static", "executor": "mock"})
    # Local MCP smoke mode: tools listed by, and executed on, the deterministic fixture MCP servers.
    async with MCPToolRegistry.connect(fixture_servers()) as registry:
        tasks, diffs = rebind_tasks(tasks, registry)
        if diffs:
            raise SystemExit(f"MCP fixture definitions differ from the static fixtures: {diffs}")
        source = {"registry": "mcp", "executor": "mcp", "servers": list(registry.server_ids)}
        return await _run(out_dir, tasks, MCPExecutor(registry), source)


async def _run(out_dir: Path, tasks, executor, tool_source: dict) -> list[dict]:
    serialization = ARCHITECTURE_MATCHED_V1
    llm = KeywordChatClient()  # one shared "LLM" for the native arm and argument generation
    pipelines = [
        NativePipeline(llm, executor, serialization),
        DecomposedPipeline(KeywordSelector(), ArgumentGenerator(llm), executor, serialization),
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "-mcp" if tool_source["registry"] == "mcp" else ""
    path = out_dir / f"smoke{suffix}-{stamp}.jsonl"
    config = ExperimentConfig(experiment_id="smoke_offline_v2", order_seeds=(None, 1, 2),
                              profile="offline_fake", condition="architecture_matched_v1", tool_source=tool_source)
    records = await run_experiment(tasks, pipelines, config, JsonlWriter(path))

    print(f"Wrote {len(records)} records to {path} (tools: {tool_source['registry']}, executor: {tool_source['executor']})")
    print(json.dumps(summarize(records), indent=2))
    freqs = selection_frequencies(records, key=lambda r: f"{r['pipeline']}::{r['task_id']}")
    print(json.dumps(freqs, indent=2))
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("results/smoke"))
    parser.add_argument("--mcp", action="store_true", help="local MCP smoke mode (deterministic fixture servers)")
    args = parser.parse_args()
    asyncio.run(main(args.out, mcp=args.mcp))
