"""Matched decomposed LLM selector: the shared LLM answers the same Choice that Jev receives.

It is built on `system-one-adapter` (TypeSafe, MIT), used as a dependency. The adapter's built-in
OpenAI provider sends neither temperature nor reasoning settings, so `ConfiguredOpenAIProvider`
subclasses it to add `shared_request_params`, the same function the native arm uses. Everything
else about the adapter's request (system prompt, `<document>` state wrapper, strict JSON schema
output) is the adapter's own and is logged per call.

Configuration that makes the arm honest:
- `normalize_probabilities=False`: verbalized probabilities are kept as written and flagged by the
  pipeline when they don't sum to 1.
- `n_retry_malformed_structure=0` and `RetryPolicy(max_retries=0)`: no hidden corrective or
  transient retries. Harness retries are explicit and logged.
- In `discrete` mode the adapter fills `probabilities` with a one-hot vector. That is not a
  distribution, so it is not reported as one.
"""

from typing import Any, Literal

import openai
from system_one_adapter import AsyncSystemOneAdapterClient
from system_one_adapter.providers.base import record_request, translating
from system_one_adapter.providers.openai import AsyncOpenAIProvider, _responses_request_kwargs, _responses_result
from typesafe_sdk import (
    Choice,
    RetryPolicy,
    TypeSafeAPIConnectionError,
    TypeSafeAPIError,
    TypeSafeAPIResponseValidationError,
    TypeSafeAPITimeoutError,
    TypeSafeError,
    TypeSafeInternalServerError,
    TypeSafeRateLimitError,
)

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import SelectorRequest
from rlcdselect.core.types import LLMConfig, ProbabilityKind, ProviderError, ProviderOutputError, TransientError, Usage
from rlcdselect.llm.openai_responses import build_client, shared_request_params
from rlcdselect.selectors.base import SelectorOutput

QUESTION_ID = "tool"

AnswerMode = Literal["discrete", "probabilities"]


class ConfiguredOpenAIProvider(AsyncOpenAIProvider):
    """The adapter's Responses provider, plus the shared model and sampling parameters."""

    def __init__(self, config: LLMConfig, *, client: openai.AsyncOpenAI | None = None) -> None:
        # Deliberately not calling super().__init__: it would construct its own SDK client.
        self.model_name = config.model
        self.api = "responses"
        self._client = build_client(client)
        self._shared = shared_request_params(config)

    async def request(self, messages, *, schema: dict[str, Any], structured: bool):
        with translating(self.translate_error):
            kwargs = _responses_request_kwargs(self.model_name, messages, schema, structured=structured)
            kwargs.update(self._shared)
            record_request(kwargs, api=self.api)
            response = await self._client.responses.create(**kwargs)
            if response.model != self.model_name:
                raise TypeSafeError(f"model_mismatch: requested {self.model_name!r}, response reports {response.model!r}")
            return _responses_result(response)


def translate_typesafe_error(exc: Exception) -> Exception:
    """Map TypeSafe SDK errors (raised by both the SDK and the adapter) to harness errors."""
    debug = getattr(exc, "debug", None)
    if isinstance(exc, (TypeSafeRateLimitError, TypeSafeInternalServerError,
                        TypeSafeAPIConnectionError, TypeSafeAPITimeoutError)):
        return TransientError(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, TypeSafeAPIResponseValidationError):
        return ProviderOutputError("malformed_output", str(exc), raw=debug if debug is not None else exc.body)
    if isinstance(exc, TypeSafeAPIError):
        if exc.status in (408, 409):
            return TransientError(f"HTTP {exc.status}: {exc}")
        return ProviderError(f"http_{exc.status}", str(exc), raw=debug if debug is not None else exc.body)
    if isinstance(exc, TypeSafeError):
        kind = "model_mismatch" if "model_mismatch" in str(exc) else "provider_error"
        return ProviderError(kind, str(exc), raw=debug)
    return exc


class MatchedLLMSelector:
    def __init__(self, config: LLMConfig, *, answer_mode: AnswerMode = "discrete",
                 client: openai.AsyncOpenAI | None = None) -> None:
        self._config = config
        self.answer_mode = answer_mode
        self._provider = ConfiguredOpenAIProvider(config, client=client)
        self._adapter = AsyncSystemOneAdapterClient(
            structured_outputs=True,
            llm_answer_mode=answer_mode,
            normalize_probabilities=False,
            n_retry_malformed_structure=0,
            retry=RetryPolicy(max_retries=0),
        )

    @property
    def selector_id(self) -> str:
        return "matched_llm"

    @property
    def model(self) -> str:
        return f"{self._config.provider}/{self._config.model}"

    @property
    def probability_kind(self) -> ProbabilityKind:
        return ProbabilityKind.LLM_VERBALIZED if self.answer_mode == "probabilities" else ProbabilityKind.NONE

    @property
    def llm_config(self) -> LLMConfig:
        return self._config

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        question = Choice(instructions=request.instructions, criteria=thaw(request.criteria))
        try:
            response = await self._adapter.system_one(
                state=thaw(request.state), questions={QUESTION_ID: question}, model=self._provider
            )
        except Exception as exc:
            translated = translate_typesafe_error(exc)
            if translated is exc:
                raise
            raise translated from exc

        answer = response.choices[QUESTION_ID]
        attempts = response.debug.get("llm_attempts", [])
        payloads = [a.get("request") for a in attempts]
        reported = None
        if attempts and isinstance(attempts[-1].get("llm_response"), dict):
            reported = attempts[-1]["llm_response"].get("model")
        u = response.usage
        verbalized = self.answer_mode == "probabilities"
        return SelectorOutput(
            choice=answer.choice,
            probabilities=dict(answer.probabilities) if verbalized else None,
            confidence=answer.confidence if verbalized else None,
            usage=Usage(
                input_tokens=getattr(u, "input_tokens_total", None),
                output_tokens=getattr(u, "output_tokens_total", None),
                extra={"n_retries": getattr(u, "n_retries", None),
                       "n_retries_malformed_structure": getattr(u, "n_retries_malformed_structure", None)},
            ),
            model_reported=reported,
            raw={"answer": answer.model_dump(mode="json"), "debug": response.debug},
            request_payload=payloads[0] if len(payloads) == 1 else payloads,
        )
