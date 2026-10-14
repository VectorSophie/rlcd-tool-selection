"""Startup verification for live runs. Fails loudly; never substitutes a model or provider."""

import os
from collections.abc import Sequence
from typing import Any

from rlcdselect.core.types import LLMConfig
from rlcdselect.llm.openrouter import SHARED_LLM_REQUIRED_PARAMETERS, OpenRouterCatalog
from rlcdselect.selectors.jev import JevSelector


class StartupError(RuntimeError):
    pass


def require_env(names: Sequence[str]) -> None:
    missing = [n for n in names if not os.environ.get(n, "").strip()]
    if missing:
        raise StartupError(f"Missing required environment variables: {missing}")


async def verify_live_models(llm: LLMConfig, jev: JevSelector | None, catalog: OpenRouterCatalog) -> dict[str, Any]:
    """Free checks via OpenRouter's endpoint listing: the shared LLM has an endpoint from the required
    provider (routing slug from `routing.only`) supporting every parameter we send; Jev has its endpoint."""
    only = list((llm.routing or {}).get("only") or [])
    if len(only) != 1:
        raise StartupError(f"Shared LLM routing must allow exactly one provider, got {only}")
    verified = {"llm": await catalog.verify(llm.model, llm.expected_upstream_provider,
                                            SHARED_LLM_REQUIRED_PARAMETERS, tag=only[0])}
    if jev is not None:
        verified["jev"] = await jev.verify_model_available()
    return verified
