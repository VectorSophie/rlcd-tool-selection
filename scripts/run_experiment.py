"""Run the core arms (native LLM, matched LLM, Jev, optional Laya) on the fixtures with real providers.

Everything goes through one OpenRouter account (`OPENROUTER_API_KEY`). Startup checks run first,
for free: the Claude endpoint from Anthropic supports every parameter we send, and Jev's endpoint
exists. During the run, any wrong provider, unexpected returned model, unroutable request or
non-zero reasoning tokens aborts the run with a `run_aborted` record.

    uv run python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --check-only
    uv run python scripts/run_experiment.py --profile deterministic_v1 --condition architecture_matched_v1 --out results/live

`--check-only` makes no paid model calls (it uses the public model-endpoint listing only).

Tools come from the static fixture registry by default. `--registry mcp` takes them from MCP
servers instead (`--mcp-fixture` for the in-process fixture servers, `--mcp-stdio ID=COMMAND` for
local stdio servers), and `--executor mcp` executes through `tools/call`. Neither mode needs any
network access beyond OpenRouter.
"""

import argparse
import asyncio
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

from rlcdselect.datasets.fixtures import core_tasks, decomposed_only_tasks, load_fixtures
from rlcdselect.datasets.mcp_fixture_server import fixture_servers
from rlcdselect.execution.mcp_executor import MCPExecutor
from rlcdselect.registry.mcp_registry import MCPToolRegistry
from rlcdselect.registry.sources import parse_stdio_server, rebind_tasks
from rlcdselect.core.types import SelectorSamplingPolicy
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
    servers = mcp_servers(args)
    async with MCPToolRegistry.connect(servers, read_timeout_seconds=60) if servers else nullcontext() as registry:
        await run_with_tools(args, profile, condition, stress, verified, tasks, registry, jev)


def mcp_servers(args: argparse.Namespace) -> dict:
    """The configured MCP servers (empty for the static registry)."""
    if args.registry == "static":
        if args.executor == "mcp" or args.mcp_fixture or args.mcp_stdio:
            raise SystemExit("--executor mcp, --mcp-fixture and --mcp-stdio need --registry mcp")
        return {}
    servers = dict(fixture_servers()) if args.mcp_fixture else {}
    for spec in args.mcp_stdio:
        server_id, params = parse_stdio_server(spec)
        if server_id in servers:
            raise SystemExit(f"Duplicate MCP server id {server_id!r}")
        servers[server_id] = params
    if not servers:
        raise SystemExit("--registry mcp needs --mcp-fixture and/or --mcp-stdio SERVER_ID=COMMAND")
    return servers


async def run_with_tools(args, profile, condition, stress, verified, tasks, registry, jev) -> None:
    tool_source = {"registry": args.registry, "executor": args.executor}
    if registry is not None:
        tasks, diffs = rebind_tasks(tasks, registry)
        tool_source["servers"] = {sid: registry.server_info(sid) for sid in registry.server_ids}
        tool_source["definition_differences_from_static"] = diffs
        print(f"Tools from MCP servers {list(registry.server_ids)}; "
              f"{len(diffs)} definition(s) differ from the static fixtures")
    seeds = tuple(None if s == "none" else int(s) for s in args.order_seeds.split(","))
    samples = args.samples or profile.samples_per_condition
    pipeline_ids = ([] if stress else ["native_llm"]) + ["matched_llm", "jev"] + (["laya"] if args.with_laya else [])
    sampling = dict(profile.selector_sampling)
    if args.jev_repetitions is not None or args.jev_execute_each_sample:
        base = sampling.get("jev") or SelectorSamplingPolicy()
        sampling["jev"] = SelectorSamplingPolicy(
            repetitions=args.jev_repetitions if args.jev_repetitions is not None else base.repetitions,
            execute_each_sample=args.jev_execute_each_sample,
            execution_sample_index=base.execution_sample_index)
    print(f"Selector sampling: { {k: f'{v.repetitions}x' + (' end-to-end' if v.execute_each_sample else ' selector-only') for k, v in sampling.items()} }")
    prices = prices_from_catalog(verified["llm"], verified.get("jev"))
    estimate = estimate_run_cost(tasks, pipeline_ids, condition, prices, len(seeds), samples, args.matched_mode,
                                 sampling)
    print(f"Estimated cost (conservative): {json.dumps(estimate, indent=2)}")
    if args.check_only:
        return
    if args.budget_usd is None:
        raise SystemExit("--budget-usd is required for live runs")
    budget = BudgetGuard(cap_usd=args.budget_usd, prices=prices)
    budget.check_estimate(estimate)

    llm = OpenRouterChatClient(profile.llm)

    executor = MCPExecutor(registry) if args.executor == "mcp" else MockExecutor()
    arguments = ArgumentGenerator(llm)
    pipelines = [] if stress else [NativePipeline(llm, executor, condition)]
    pipelines += [
        # One OpenRouter SDK client serves native calling, argument generation and matched selection.
        DecomposedPipeline(MatchedLLMSelector(profile.llm, answer_mode=args.matched_mode, client=llm.sdk_client),
                           arguments, executor, condition),
        DecomposedPipeline(jev, arguments, executor, condition, sampling=sampling.get("jev", SelectorSamplingPolicy())),
    ]
    if args.with_laya:
        from rlcdselect.selectors.laya import LayaSelector

        pipelines.append(DecomposedPipeline(LayaSelector(device=args.laya_device), arguments, executor, condition))

    config = ExperimentConfig(
        experiment_id=f"{profile.name}__{args.condition}", order_seeds=seeds,
        samples_per_condition=samples, profile=profile.name, condition=args.condition, tool_source=tool_source,
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
    parser.add_argument("--jev-selector-repetitions", "--jev-repetitions", dest="jev_repetitions", type=int,
                        default=None, help="identical Jev selection calls per run (selector-only); overrides the "
                        "profile. Development default 5, pilot recommendation 10; final N is chosen from "
                        "external-dataset variance")
    parser.add_argument("--jev-execute-each-sample", action="store_true",
                        help="also generate arguments and execute for every Jev draw (multiplies argument-LLM cost)")
    parser.add_argument("--with-laya", action="store_true")
    parser.add_argument("--laya-device", default="cuda:1")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--budget-usd", type=float, default=None,
                        help="hard cap for this run; refused up front if the estimate exceeds it")
    parser.add_argument("--registry", choices=["static", "mcp"], default="static",
                        help="where tool definitions come from (static fixtures, or the configured MCP servers)")
    parser.add_argument("--executor", choices=["mock", "mcp"], default="mock",
                        help="mock: schema check and canned result; mcp: real tools/call (needs --registry mcp)")
    parser.add_argument("--mcp-fixture", action="store_true",
                        help="serve the fixture tools from the deterministic local MCP fixture servers (in-process)")
    parser.add_argument("--mcp-stdio", action="append", default=[], metavar="SERVER_ID=COMMAND",
                        help="a local MCP server over stdio, e.g. 'mail=python -m rlcdselect.datasets.mcp_fixture_server mail'")
    parser.add_argument("--out", default="results/live")
    asyncio.run(main(parser.parse_args()))
