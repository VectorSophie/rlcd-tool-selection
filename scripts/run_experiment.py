"""Run the core arms (native LLM, matched LLM, Jev, optional Laya) on the fixtures with real providers.

Startup checks run first: required API keys, then the availability of the pinned OpenAI and Jev
models. Any failure stops the run before a single task executes.

    uv run python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --check-only
    uv run python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --out results/live

`--check-only` makes no paid model calls (it uses the model listing endpoints only).
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rlcdselect.datasets.fixtures import core_tasks, decomposed_only_tasks, load_fixtures
from rlcdselect.eval.logging import JsonlWriter
from rlcdselect.eval.metrics import summarize
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.openai_responses import OpenAIResponsesClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import CONDITIONS, PROFILES
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.selectors.matched_llm import MatchedLLMSelector
from rlcdselect.startup import require_env, verify_live_models


async def main(args: argparse.Namespace) -> None:
    profile = PROFILES[args.profile]
    condition = CONDITIONS[args.condition]
    stress = condition.allow_duplicate_names
    require_env(["OPENAI_API_KEY", "TYPESAFE_API_KEY"])

    llm = OpenAIResponsesClient(profile.llm)
    jev = JevSelector()
    verified = await verify_live_models(llm, jev)
    print(f"Verified pinned models: {verified}")
    if args.check_only:
        return

    executor = MockExecutor()
    arguments = ArgumentGenerator(llm)
    pipelines = [] if stress else [NativePipeline(llm, executor, condition)]
    pipelines += [
        DecomposedPipeline(MatchedLLMSelector(profile.llm, answer_mode=args.matched_mode), arguments, executor, condition),
        DecomposedPipeline(jev, arguments, executor, condition),
    ]
    if args.with_laya:
        from rlcdselect.selectors.laya import LayaSelector

        pipelines.append(DecomposedPipeline(LayaSelector(device=args.laya_device), arguments, executor, condition))

    _, tasks = load_fixtures()
    tasks = decomposed_only_tasks(tasks) if stress else core_tasks(tasks)
    seeds = tuple(None if s == "none" else int(s) for s in args.order_seeds.split(","))
    config = ExperimentConfig(
        experiment_id=f"{profile.name}__{args.condition}", order_seeds=seeds,
        samples_per_condition=args.samples or profile.samples_per_condition,
        profile=profile.name, condition=args.condition,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(args.out) / f"{config.experiment_id}__{stamp}.jsonl"
    records = await run_experiment(tasks, pipelines, config, JsonlWriter(path))
    print(f"Wrote {len(records)} records to {path}")
    print(json.dumps(summarize(records), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    parser.add_argument("--matched-mode", choices=["discrete", "probabilities"], default="discrete")
    parser.add_argument("--order-seeds", default="none", help="comma-separated, 'none' = canonical order")
    parser.add_argument("--samples", type=int, default=None, help="override the profile's samples per condition")
    parser.add_argument("--with-laya", action="store_true")
    parser.add_argument("--laya-device", default="cuda:1")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--out", default="results/live")
    asyncio.run(main(parser.parse_args()))
