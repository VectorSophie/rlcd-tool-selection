"""Laya selector (secondary arm): local, open-weight RLCD model, pinned to a checkpoint revision.

The `laya` package is an optional extra (`uv sync --extra laya`) and is imported lazily.
`laya.Agent` is used directly with an explicit checkpoint and revision. Laya's `Router` is not
used, because it would choose a checkpoint by detected language.

Laya reports when it truncated the state (`usage.truncated`) or collapsed options under its
192-256-token option budget (`usage.options`). Both are kept in `raw` and summarized in `usage.extra`
so trimmed runs can be excluded from primary analysis. Laya rounds probabilities to 4 decimals.
"""

import asyncio
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import SelectorRequest
from rlcdselect.core.types import LLMConfig, ProbabilityKind, ProviderOutputError, Usage
from rlcdselect.selectors.base import SelectorOutput

LAYA_CHECKPOINT = "convaiinnovations/laya"
QUESTION_ID = "tool"


class LayaSelector:
    def __init__(self, checkpoint: str = LAYA_CHECKPOINT, *, revision: str | None = None,
                 device: str | None = None, agent: Any = None) -> None:
        """`agent` may be injected (tests); otherwise a pinned `laya.Agent` is loaded on first use."""
        if agent is None and revision is None:
            from laya import PINNED_REVISIONS  # lazy: optional extra

            revision = PINNED_REVISIONS[checkpoint]
        self.checkpoint = checkpoint
        self.revision = revision
        self.device = device
        self._agent = agent
        self._lock = asyncio.Lock()

    def _load(self) -> Any:
        if self._agent is None:
            from laya import Agent  # lazy: optional extra

            self._agent = Agent(self.checkpoint, device=self.device, revision=self.revision)
        return self._agent

    @property
    def selector_id(self) -> str:
        return "laya"

    @property
    def model(self) -> str:
        return f"{self.checkpoint}@{self.revision}"

    @property
    def probability_kind(self) -> ProbabilityKind:
        return ProbabilityKind.RLCD_NATIVE

    @property
    def llm_config(self) -> LLMConfig | None:
        return None

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        questions = {QUESTION_ID: {"type": "choice", "instructions": request.instructions,
                                   "criteria": thaw(request.criteria)}}
        state = thaw(request.state)
        async with self._lock:  # one forward pass at a time on the shared model
            agent = await asyncio.to_thread(self._load)
            result = await asyncio.to_thread(agent.system_one, state, questions)
        answer = (result.get("answers") or {}).get(QUESTION_ID)
        if not isinstance(answer, dict) or "choice" not in answer:
            raise ProviderOutputError("malformed_output", "Laya returned no choice answer", raw=result)
        usage = result.get("usage") or {}
        return SelectorOutput(
            choice=answer["choice"],
            probabilities=answer.get("probabilities"),
            confidence=answer.get("confidence"),
            usage=Usage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                extra={
                    "truncated": usage.get("truncated"),
                    "state_tokens_dropped": usage.get("state_tokens_dropped"),
                    "options_collapsed": (usage.get("options") or {}).get(QUESTION_ID),
                    "answer_confidence": answer.get("answer_confidence"),
                },
            ),
            model_reported=result.get("model"),
            raw=result,
            request_payload={"state": state, "questions": questions, "checkpoint": self.checkpoint,
                             "revision": self.revision},
        )
