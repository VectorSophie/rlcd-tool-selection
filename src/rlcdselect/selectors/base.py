"""Decomposed selector protocol.

A selector receives a `SelectorRequest`, the only representation of the candidates it gets, and
returns the option id it chose plus whatever probabilities it natively produces. Validation of the
output (an unknown choice, malformed probabilities) happens in the pipeline, not in the selector, so
every selector is judged by the same rules.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from rlcdselect.core.serialization import SelectorRequest
from rlcdselect.core.types import LLMConfig, ProbabilityKind, Usage


@dataclass(frozen=True)
class SelectorOutput:
    choice: str  # an option id from the request's criteria (candidate id or abstain id)
    probabilities: Mapping[str, float] | None
    confidence: float | None
    usage: Usage | None
    model_reported: str | None
    raw: Any
    request_payload: Any = None  # the exact payload sent to the provider, when one was sent
    provider_meta: Mapping[str, Any] | None = None  # requested/returned model, provider, request id


class Selector(Protocol):
    @property
    def selector_id(self) -> str:
        """Stable identifier, e.g. 'jev', 'matched_llm', 'laya', 'mock_keyword'."""
        ...

    @property
    def model(self) -> str:
        """The pinned model identifier requested."""
        ...

    @property
    def probability_kind(self) -> ProbabilityKind: ...

    @property
    def llm_config(self) -> LLMConfig | None:
        """The LLM config when the selector is LLM-backed; None for RLCD and mock selectors."""
        ...

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        """Make exactly one selection call. Raise `TransientError` for retryable failures."""
        ...
