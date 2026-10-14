"""Offline end-to-end smoke run over the static fixtures. No network, no API keys.

Arms: native (fake keyword LLM) and decomposed (keyword mock selector + the same fake LLM for
arguments). The fakes' decisions are not a model's; this checks wiring, logging and metrics only.

    uv run python scripts/smoke_offline.py [--out results/smoke]
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rlcdselect.datasets.fixtures import core_tasks, load_fixtures
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


async def main(out_dir: Path) -> None:
    _, tasks = load_fixtures()
    tasks = core_tasks(tasks)  # decomposed-only stress tasks are excluded from cross-arm runs
    serialization = ARCHITECTURE_MATCHED_V1
    llm = KeywordChatClient()  # one shared "LLM" for the native arm and argument generation
    executor = MockExecutor()
    pipelines = [
        NativePipeline(llm, executor, serialization),
        DecomposedPipeline(KeywordSelector(), ArgumentGenerator(llm), executor, serialization),
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"smoke-{stamp}.jsonl"
    config = ExperimentConfig(experiment_id="smoke_offline_v2", order_seeds=(None, 1, 2),
                              profile="offline_fake", condition="architecture_matched_v1")
    records = await run_experiment(tasks, pipelines, config, JsonlWriter(path))

    print(f"Wrote {len(records)} records to {path}")
    print(json.dumps(summarize(records), indent=2))
    freqs = selection_frequencies(records, key=lambda r: f"{r['pipeline']}::{r['task_id']}")
    print(json.dumps(freqs, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("results/smoke"))
    asyncio.run(main(parser.parse_args().out))
