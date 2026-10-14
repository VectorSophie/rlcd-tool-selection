"""Jev selector through the official TypeSafe SDK, pinned to an exact model id.

- Aliases (`*-latest`) are refused. `verify_model_available` checks that the pinned id is in the
  account's `/v1/models` list and fails with that list otherwise. There is no fallback.
- SDK retries are disabled (`RetryPolicy(max_retries=0)`); retries belong to the harness.
- A response reporting a different model id is an error.
- The exact HTTP request body sent is recovered from the SDK's raw response and logged.
  Headers, including credentials, are not logged.
"""

import json

from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import SelectorRequest
from rlcdselect.core.types import LLMConfig, ProbabilityKind, ProviderError, Usage
from rlcdselect.llm.openai_responses import ModelUnavailableError
from rlcdselect.profiles import JEV_MODEL
from rlcdselect.selectors.base import SelectorOutput
from rlcdselect.selectors.matched_llm import QUESTION_ID, translate_typesafe_error

NO_RETRY = RetryPolicy(max_retries=0)


class JevSelector:
    def __init__(self, model: str = JEV_MODEL, *, client: AsyncTypeSafeClient | None = None) -> None:
        if "latest" in model:
            raise ValueError(f"Jev must be pinned to an exact model id, got {model!r}")
        self._model = model
        self._client = client or AsyncTypeSafeClient(retry=NO_RETRY)

    @property
    def selector_id(self) -> str:
        return "jev"

    @property
    def model(self) -> str:
        return self._model

    @property
    def probability_kind(self) -> ProbabilityKind:
        return ProbabilityKind.RLCD_NATIVE

    @property
    def llm_config(self) -> LLMConfig | None:
        return None

    async def available_models(self) -> list[str]:
        try:
            listing = await self._client.models.list(retry=NO_RETRY)
        except Exception as exc:
            translated = translate_typesafe_error(exc)
            if translated is exc:
                raise
            raise translated from exc
        return [m.name for m in listing.models]

    async def verify_model_available(self) -> None:
        names = await self.available_models()
        if self._model not in names:
            raise ModelUnavailableError(
                f"Pinned Jev model {self._model!r} is not available to this account. Available models: {names}"
            )

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        question = Choice(instructions=request.instructions, criteria=thaw(request.criteria))
        try:
            response = await self._client.system_one(
                state=thaw(request.state), questions={QUESTION_ID: question}, model=self._model, retry=NO_RETRY
            )
        except Exception as exc:
            translated = translate_typesafe_error(exc)
            if translated is exc:
                raise
            raise translated from exc

        http = response.raw_http_response
        sent = json.loads(http.request.content)
        received = json.loads(http.content)
        if response.model != self._model:
            raise ProviderError("model_mismatch",
                                f"Requested {self._model!r} but the response reports {response.model!r}", raw=received)
        answer = response.choices[QUESTION_ID]
        return SelectorOutput(
            choice=answer.choice,
            probabilities=dict(answer.probabilities),
            confidence=answer.confidence,
            usage=Usage(response.usage.input_tokens, response.usage.output_tokens),
            model_reported=response.model,
            raw=received,
            request_payload=sent,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
