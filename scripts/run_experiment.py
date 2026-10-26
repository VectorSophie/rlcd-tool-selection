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
from rlcdselect.core.jsonutil import thaw
from rlcdselect.datasets.external.registry import DATASETS
from rlcdselect.datasets.mcp_fixture_server import fixture_servers
from rlcdselect.eval.budget import Prices
from rlcdselect.eval.logging import read_jsonl
from rlcdselect.eval.pilot import (
    DEFAULT_APPROVED_LIMIT_USD,
    allocate_caps,
    estimate_report,
    execute_group,
    freeze,
    plan_group,
    verify_manifest,
)
from rlcdselect.profiles import PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS
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
    if args.manifest:
        args.profile = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["profile"]
    if args.profile is None:
        raise SystemExit("--profile is required")
    profile = PROFILES[args.profile]
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

    if args.manifest:  # execute a frozen external-dataset manifest
        return await run_manifest(Path(args.manifest), profile, jev)
    if args.dataset:  # plan one external-dataset group: sample, estimate, freeze; no model calls
        prices = prices_from_catalog(verified["llm"], verified.get("jev"))
        datasets = [(d.partition(":")[0], int(d.partition(":")[2]) if d.partition(":")[2] else args.sample_size)
                    for d in args.dataset]
        plan = plan_group(args.group_name, datasets, seed=args.seed, stratify=args.stratify, profile=profile,
                          jev_repetitions=args.jev_repetitions or PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS,
                          prices=prices)
        allocate_caps([plan], limit_usd=args.budget_usd or DEFAULT_APPROVED_LIMIT_USD)
        out = Path(args.plan_dir) / args.group_name
        path = freeze(plan, out)
        (out / "estimate.md").write_text(estimate_report([plan]), encoding="utf-8")
        print(estimate_report([plan]))
        print(f"Frozen manifest {path} (hash {json.loads(path.read_text())['manifest_hash'][:16]}). "
              f"Nothing was run; execute with --manifest {path}")
        return

    if args.condition is None:
        raise SystemExit("--condition is required for fixture runs")
    condition = CONDITIONS[args.condition]
    stress = condition.allow_duplicate_names
    _, all_tasks = load_fixtures()
    tasks = decomposed_only_tasks(all_tasks) if stress else core_tasks(all_tasks)
    servers = mcp_servers(args)
    async with MCPToolRegistry.connect(servers, read_timeout_seconds=60) if servers else nullcontext() as registry:
        await run_with_tools(args, profile, condition, stress, verified, tasks, registry, jev)


async def run_manifest(path: Path, profile, jev: JevSelector) -> None:
    """Verify a frozen manifest against the code, data and estimate, then run it. Results go next
    to the manifest; an existing records file stops the run (run sets are never mixed)."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["llm_config"] != thaw(profile.llm):
        raise SystemExit("The profile's LLM config differs from the manifest")
    prices = Prices(**manifest["prices"])
    samples = verify_manifest(manifest, prices)
    print(f"Manifest {manifest['manifest_hash'][:16]} verified: commit {manifest['git_commit'][:12]}, "
          f"{sum(len(s.tasks) for s in samples)} tasks, estimate ${manifest['estimate_usd']:.4f}, "
          f"cap ${manifest['budget_cap_usd']:.4f}")
    llm = OpenRouterChatClient(profile.llm)
    arguments = ArgumentGenerator(llm)
    executor = MockExecutor()
    matched = MatchedLLMSelector(profile.llm, client=llm.sdk_client)  # one SDK client for every LLM role

    def make_pipelines(serialization, jev_sampling):
        return [NativePipeline(llm, executor, serialization),
                DecomposedPipeline(matched, arguments, executor, serialization),
                DecomposedPipeline(jev, arguments, executor, serialization, sampling=jev_sampling)]

    records_path = path.parent / "records.jsonl"
    budget = None
    try:
        records, budget = await execute_group(manifest, samples, make_pipelines, records_path, prices=prices)
        print(f"Wrote {len(records)} records to {records_path}")
    finally:
        spent = read_jsonl(records_path)[-1].get("budget_spent_usd") if records_path.exists() else None
        print(f"Spend so far: {spent}  (estimate ${manifest['estimate_usd']:.4f}, cap ${manifest['budget_cap_usd']:.4f})")


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
    parser.add_argument("--profile", choices=sorted(PROFILES), default=None)
    parser.add_argument("--condition", choices=sorted(CONDITIONS), default=None,
                        help="fixture runs only; external datasets carry their own condition")
    parser.add_argument("--dataset", action="append", default=[], metavar="NAME[:N]",
                        help=f"plan an external-dataset group (no model calls): {', '.join(sorted(DATASETS))}")
    parser.add_argument("--sample-size", type=int, default=None, help="default per-dataset size when NAME has no :N")
    parser.add_argument("--seed", type=int, default=20261026, help="sampling and per-task order seed")
    parser.add_argument("--stratify", action=argparse.BooleanOptionalAction, default=True,
                        help="stratify by source label where the dataset defines strata (When2Call 50/50/50)")
    parser.add_argument("--group-name", default="group", help="name of the planned run group")
    parser.add_argument("--plan-dir", default="results/external_pilot", help="where frozen manifests are written")
    parser.add_argument("--manifest", default=None, help="execute a frozen external-dataset manifest")
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
                        help="fixture runs: hard cap, refused up front if the estimate exceeds it; dataset planning: the approved limit (default 10)")
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
