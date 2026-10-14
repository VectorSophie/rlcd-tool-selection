"""Jev selector through the official TypeSafe SDK, routed via OpenRouter's System One API.

- Base URL `https://openrouter.ai/api`; the SDK appends `/v1/systemone`. Authenticated with the
  OpenRouter key.
- The model id must be pinned. Aliases (`latest`, `~` prefix) are refused.
- Startup: `verify_model_available` checks OpenRouter's public endpoint listing for a `TypeSafe`
  endpoint for the model. The TypeSafe SDK's own `models.list()` does not work against OpenRouter,
  per OpenRouter's docs.
- These abort the run (`FatalRunError`): an upstream provider other than `TypeSafe`, a returned model
  id outside `expected_returned_models` (OpenRouter documents `typesafe/jev-1.13-20260917` as the
  build behind `typesafe/jev-1.13`), or a 404 routing failure.
- SDK retries are disabled. The exact request body is recovered from the raw HTTP exchange and
  logged, without headers.
"""

import json
import os

from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy, TypeSafeNotFoundError

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import SelectorRequest
from rlcdselect.core.types import FatalRunError, LLMConfig, ProbabilityKind, Usage
from rlcdselect.llm.openrouter import ModelUnavailableError, OpenRouterCatalog
from rlcdselect.profiles import JEV_EXPECTED_PROVIDER, JEV_EXPECTED_RETURNED_MODELS, JEV_MODEL
from rlcdselect.selectors.base import SelectorOutput
from rlcdselect.selectors.matched_llm import QUESTION_ID, translate_typesafe_error

NO_RETRY = RetryPolicy(max_retries=0)
OPENROUTER_SYSTEM_ONE_BASE_URL = "https://openrouter.ai/api"


class JevSelector:
    def __init__(
        self,
        model: str = JEV_MODEL,
        *,
        expected_returned_models: tuple[str, ...] = JEV_EXPECTED_RETURNED_MODELS,
        expected_provider: str = JEV_EXPECTED_PROVIDER,
        client: AsyncTypeSafeClient | None = None,
        catalog: OpenRouterCatalog | None = None,
    ) -> None:
        if "latest" in model or model.startswith("~"):
            raise ValueError(f"Jev must be pinned to an exact model id, got {model!r}")
        self._model = model
        self.expected_returned_models = tuple(expected_returned_models)
        self.expected_provider = expected_provider
        self._client = client or AsyncTypeSafeClient(
            api_key=os.environ.get("OPENROUTER_API_KEY"), base_url=OPENROUTER_SYSTEM_ONE_BASE_URL, retry=NO_RETRY
        )
        self._catalog = catalog

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

    async def verify_model_available(self) -> dict:
        catalog = self._catalog or OpenRouterCatalog()
        try:
            return await catalog.verify(self._model, self.expected_provider)
        finally:
            if self._catalog is None:
                await catalog.aclose()

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        question = Choice(instructions=request.instructions, criteria=thaw(request.criteria))
        try:
            response = await self._client.system_one(
                state=thaw(request.state), questions={QUESTION_ID: question}, model=self._model, retry=NO_RETRY
            )
        except TypeSafeNotFoundError as exc:
            raise FatalRunError("routing_rejected", f"OpenRouter could not route {self._model!r}: {exc}",
                                raw=exc.body) from exc
        except Exception as exc:
            translated = translate_typesafe_error(exc)
            if translated is exc:
                raise
            raise translated from exc

        http = response.raw_http_response
        sent = json.loads(http.request.content)
        received = json.loads(http.content)
        usage = received.get("usage") or {}
        meta = {
            "gateway": "openrouter",
            "requested_model": self._model,
            "returned_model": received.get("model"),
            "provider": received.get("provider"),
            "provider_source": "response" if received.get("provider") is not None else None,
            "generation_id": received.get("id"),
            "request_id": None,
            "cost": usage.get("cost"),
        }
        if meta["provider"] != self.expected_provider:
            raise FatalRunError("provider_mismatch",
                                f"Expected Jev provider {self.expected_provider!r}, got {meta['provider']!r}", raw=meta)
        if received.get("model") not in self.expected_returned_models:
            raise FatalRunError("model_mismatch",
                                f"Jev returned model {received.get('model')!r}, expected {list(self.expected_returned_models)}",
                                raw=meta)
        answer = response.choices[QUESTION_ID]
        return SelectorOutput(
            choice=answer.choice,
            probabilities=dict(answer.probabilities),
            confidence=answer.confidence,
            usage=Usage(response.usage.input_tokens, response.usage.output_tokens, extra={"cost": usage.get("cost")}),
            model_reported=received.get("model"),
            raw=received,
            request_payload=sent,
            provider_meta=meta,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["JevSelector", "ModelUnavailableError", "OPENROUTER_SYSTEM_ONE_BASE_URL"]
