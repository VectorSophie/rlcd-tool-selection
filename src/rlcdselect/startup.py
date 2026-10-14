"""Startup verification for live runs. Fails loudly; never substitutes a model."""

import os
from collections.abc import Sequence

from rlcdselect.llm.openai_responses import OpenAIResponsesClient
from rlcdselect.selectors.jev import JevSelector


class StartupError(RuntimeError):
    pass


def require_env(names: Sequence[str]) -> None:
    missing = [n for n in names if not os.environ.get(n, "").strip()]
    if missing:
        raise StartupError(f"Missing required environment variables: {missing}")


async def verify_live_models(llm: OpenAIResponsesClient | None, jev: JevSelector | None) -> dict[str, str]:
    """Check that every pinned model is available to this account. Returns what was verified."""
    verified = {}
    if llm is not None:
        await llm.verify_model_available()
        verified["openai"] = llm.config.model
    if jev is not None:
        await jev.verify_model_available()
        verified["jev"] = jev.model
    return verified
