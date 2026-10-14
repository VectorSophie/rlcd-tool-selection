"""Offline selectors for tests and smoke runs."""

from collections.abc import Callable, Iterable
from typing import Any

from rlcdselect.core.jsonutil import canonical_json
from rlcdselect.core.serialization import SelectorRequest
from rlcdselect.core.types import LLMConfig, ProbabilityKind, Usage
from rlcdselect.llm.fake import best_match, strings_in
from rlcdselect.selectors.base import SelectorOutput


class KeywordSelector:
    """Picks the criterion with the most word overlap with the state, or abstains below threshold.

    It scores only the criterion text it was given, so it is sensitive to the configured
    representation exactly as a real selector would be.
    """

    def __init__(self, threshold: int = 2) -> None:
        self.threshold = threshold
        self.requests: list[SelectorRequest] = []

    @property
    def selector_id(self) -> str:
        return "mock_keyword"

    @property
    def model(self) -> str:
        return "keyword-v1"

    @property
    def probability_kind(self) -> ProbabilityKind:
        return ProbabilityKind.NONE

    @property
    def llm_config(self) -> LLMConfig | None:
        return None

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        self.requests.append(request)
        text = " ".join(strings_in(request.state))
        options = [
            (cid, crit if isinstance(crit, str) else canonical_json(crit))
            for cid, crit in request.criteria.items()
            if cid != request.abstain_id
        ]
        chosen, scores = best_match(text, options, self.threshold)
        if chosen is None:
            if request.abstain_id is None:
                chosen = options[0][0]
            else:
                chosen = request.abstain_id
        return SelectorOutput(chosen, None, None, Usage(0, 0), self.model, raw={"scores": scores})


ScriptStep = SelectorOutput | Exception | Callable[[SelectorRequest], SelectorOutput]


class ScriptedSelector:
    """Returns (or raises) scripted outputs in order; records every request."""

    def __init__(
        self,
        steps: Iterable[ScriptStep],
        *,
        selector_id: str = "mock_scripted",
        probability_kind: ProbabilityKind = ProbabilityKind.MOCK,
    ) -> None:
        self._steps = list(steps)
        self._selector_id = selector_id
        self._probability_kind = probability_kind
        self.requests: list[SelectorRequest] = []

    @property
    def selector_id(self) -> str:
        return self._selector_id

    @property
    def model(self) -> str:
        return "scripted"

    @property
    def probability_kind(self) -> ProbabilityKind:
        return self._probability_kind

    @property
    def llm_config(self) -> LLMConfig | None:
        return None

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        self.requests.append(request)
        if not self._steps:
            raise AssertionError("ScriptedSelector ran out of scripted steps")
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        if callable(step):
            return step(request)
        return step


def output(choice: str, probabilities: dict[str, float] | None = None, raw: Any = None) -> SelectorOutput:
    """Convenience constructor for scripted outputs."""
    return SelectorOutput(choice, probabilities, None, Usage(1, 1), "scripted", raw)
