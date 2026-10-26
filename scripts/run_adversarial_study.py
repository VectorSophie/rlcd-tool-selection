"""Execute one frozen adversarial-study manifest (paid). Verifies the manifest against the code, the
data, the pre-registration and the estimate first; refuses an existing records file; and caps
spend at min(the group's nominal cap, the global cap minus everything this study has already
recorded).

    uv run --extra laya python scripts/run_adversarial_study.py results/adversarial_study/A_clean/manifest.json
"""

import argparse
import asyncio
import json
from pathlib import Path

from rlcdselect.eval.adversarial import effective_cap, execute, study_spend, verify
from rlcdselect.eval.budget import Prices
from rlcdselect.eval.logging import read_jsonl
from rlcdselect.execution.mock import MockExecutor
from rlcdselect.generation.arguments import ArgumentGenerator
from rlcdselect.llm.openrouter import OpenRouterCatalog, OpenRouterChatClient
from rlcdselect.pipelines.decomposed import DecomposedPipeline
from rlcdselect.pipelines.native import NativePipeline
from rlcdselect.profiles import PROFILES
from rlcdselect.selectors.jev import JevSelector
from rlcdselect.selectors.matched_llm import SYSTEMONE_ARM_ID, MatchedLLMSelector
from rlcdselect.selectors.matched_neutral import MatchedNeutralSelector
from rlcdselect.startup import load_dotenv, require_env, verify_live_models

ROOT = Path(__file__).resolve().parent.parent


async def main(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    profile = PROFILES[manifest["profile"]]
    load_dotenv(ROOT / ".env")
    require_env(["OPENROUTER_API_KEY"])
    jev = JevSelector()
    catalog = OpenRouterCatalog()
    try:
        await verify_live_models(profile.llm, jev, catalog)
    finally:
        await catalog.aclose()
    prices = Prices(**manifest["prices"])
    verified = verify(manifest, profile, prices)
    study_dir = path.parent.parent
    print(f"Manifest {manifest['manifest_hash'][:16]} verified: group {manifest['group']}, commit "
          f"{manifest['git_commit'][:12]}, estimate ${manifest['estimate_usd']:.4f}, nominal cap "
          f"${manifest['budget_cap_usd']:.4f}, study spend so far ${study_spend(study_dir):.4f}, effective cap "
          f"${effective_cap(manifest, study_dir):.4f}")
    llm = OpenRouterChatClient(profile.llm)
    arguments = ArgumentGenerator(llm)
    executor = MockExecutor()
    # One OpenRouter SDK client and one LLMConfig serve every Claude role.
    systemone = MatchedLLMSelector(profile.llm, client=llm.sdk_client, selector_id=SYSTEMONE_ARM_ID)
    neutral = MatchedNeutralSelector(profile.llm, client=llm.sdk_client)

    def make_pipelines(serialization, jev_sampling):
        return [NativePipeline(llm, executor, serialization),
                DecomposedPipeline(systemone, arguments, executor, serialization),
                DecomposedPipeline(neutral, arguments, executor, serialization),
                DecomposedPipeline(jev, arguments, executor, serialization, sampling=jev_sampling)]

    records_path = path.parent / "records.jsonl"
    try:
        records, budget = await execute(manifest, verified, make_pipelines, records_path, study_dir=study_dir,
                                        prices=prices)
        print(f"Wrote {len(records)} records to {records_path}; spend {json.dumps(budget.summary())}")
    finally:
        spent = read_jsonl(records_path)[-1].get("budget_spent_usd") if records_path.exists() else None
        print(f"Group spend: {spent}; study spend now ${study_spend(study_dir):.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    asyncio.run(main(Path(parser.parse_args().manifest)))
