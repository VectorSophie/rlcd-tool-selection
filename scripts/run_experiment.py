"""Run the core arms (native LLM, matched LLM, Jev, optional Laya) on the fixtures with real providers.

Everything goes through one OpenRouter account (`OPENROUTER_API_KEY`). Startup checks run first,
for free: the Claude endpoint from Anthropic supports every parameter we send, and Jev's endpoint
exists. During the run, any wrong provider, unexpected returned model, unroutable request or
non-zero reasoning tokens aborts the run with a `run_aborted` record.

    uv run python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --check-only
    uv run python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --out results/live

`--check-only` makes no paid model calls (it uses the public model-endpoint listing only).
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rlcdselect.datasets.fixtures import core_tasks, decomposed_only_tasks, load_fixtures
from rlcdselect.eval.budget import BudgetGuard, estimate_run_cost, prices_from_catalog
from rlcdselect.eval.logging import JsonlWriter
from rlcdselect.eval.metrics import summarize
from rlcdselect.eval.runner import ExperimentConfig, run_experiment
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.openrouter import OpenRouterCatalog, OpenRouterChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import CONDITIONS, PROFILES
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.selectors.matched_llm import MatchedLLMSelector
from rlcdselect.startup import load_dotenv, require_env, verify_live_models


async def main(args: argparse.Namespace) -> None:
    profile = PROFILES[args.profile]
    condition = CONDITIONS[args.condition]
    stress = condition.allow_duplicate_names
    if loaded := load_dotenv(Path(__file__).resolve().parent.parent / ".env"):
        print(f"Loaded from .env: {loaded}")
    require_env(["OPENROUTER_API_KEY"])

    jev = JevSelector()
    catalog = OpenRouterCatalog()
    try:
        verified = await verify_live_models(profile.llm, jev, catalog)
    finally:
        await catalog.aclose()
    print(f"Verified (no paid calls): {json.dumps(verified, indent=2)}")

    _, all_tasks = load_fixtures()
    tasks = decomposed_only_tasks(all_tasks) if stress else core_tasks(all_tasks)
    seeds = tuple(None if s == "none" else int(s) for s in args.order_seeds.split(","))
    samples = args.samples or profile.samples_per_condition
    pipeline_ids = ([] if stress else ["native_llm"]) + ["matched_llm", "jev"] + (["laya"] if args.with_laya else [])
    prices = prices_from_catalog(verified["llm"], verified.get("jev"))
    estimate = estimate_run_cost(tasks, pipeline_ids, condition, prices, len(seeds), samples, args.matched_mode)
    print(f"Estimated cost (conservative): {json.dumps(estimate, indent=2)}")
    if args.check_only:
        return
    if args.budget_usd is None:
        raise SystemExit("--budget-usd is required for live runs")
    budget = BudgetGuard(cap_usd=args.budget_usd, prices=prices)
    budget.check_estimate(estimate)

    llm = OpenRouterChatClient(profile.llm)

    executor = MockExecutor()
    arguments = ArgumentGenerator(llm)
    pipelines = [] if stress else [NativePipeline(llm, executor, condition)]
    pipelines += [
        # One OpenRouter SDK client serves native calling, argument generation and matched selection.
        DecomposedPipeline(MatchedLLMSelector(profile.llm, answer_mode=args.matched_mode, client=llm.sdk_client),
                           arguments, executor, condition),
        DecomposedPipeline(jev, arguments, executor, condition),
    ]
    if args.with_laya:
        from rlcdselect.selectors.laya import LayaSelector

        pipelines.append(DecomposedPipeline(LayaSelector(device=args.laya_device), arguments, executor, condition))

    config = ExperimentConfig(
        experiment_id=f"{profile.name}__{args.condition}", order_seeds=seeds,
        samples_per_condition=samples, profile=profile.name, condition=args.condition,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(args.out) / f"{config.experiment_id}__{stamp}.jsonl"
    try:
        records = await run_experiment(tasks, pipelines, config, JsonlWriter(path), budget=budget)
    finally:
        print(f"Spend: {json.dumps(budget.summary(), indent=2)}  (estimate was ${estimate['total_usd']:.4f})")
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
    parser.add_argument("--budget-usd", type=float, default=None,
                        help="hard cap for this run; refused up front if the estimate exceeds it")
    parser.add_argument("--out", default="results/live")
    asyncio.run(main(parser.parse_args()))
