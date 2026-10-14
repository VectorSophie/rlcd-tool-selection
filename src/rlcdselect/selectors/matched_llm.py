"""Matched decomposed LLM selector: the shared LLM answers the same Choice that Jev receives.

It is built on `system-one-adapter` (TypeSafe, MIT), used as a dependency, through its
OpenAI-compatible chat-completions path pointed at OpenRouter. The adapter's provider sends only
model, messages and response_format, so `ConfiguredChatProvider` subclasses it to add
`shared_request_params` (model, temperature, max_tokens, thinking, Anthropic-only routing), the same
function the native arm uses. It also applies the same served-by checks: provider, returned model,
and no reasoning tokens. Everything else (system prompt, `<document>` state wrapper, strict JSON
schema output) is the adapter's own and is logged per call.

Configuration that makes the arm honest:
- `normalize_probabilities=False`: verbalized probabilities are kept as written and flagged by the
  pipeline when they don't sum to 1.
- `n_retry_malformed_structure=0` and `RetryPolicy(max_retries=0)`: no hidden corrective or
  transient retries. Harness retries are explicit and logged.
- In `discrete` mode the adapter fills `probabilities` with a one-hot vector. That is not a
  distribution, so it is not reported as one.
"""

import asyncio
import json
from typing import Any, Literal

import openai
from system_one_adapter import AsyncSystemOneAdapterClient
from system_one_adapter.providers.base import record_request, render_messages, translating
from system_one_adapter.providers.openai import AsyncOpenAIProvider, _response_format, _result
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
from rlcdselect.core.types import (
    FatalRunError,
    LLMConfig,
    ProbabilityKind,
    ProviderError,
    ProviderOutputError,
    TransientError,
    Usage,
)
from rlcdselect.llm.openrouter import build_client, check_served, shared_request_params, split_sdk_kwargs, translate_openrouter_error
from rlcdselect.selectors.base import SelectorOutput

QUESTION_ID = "tool"

AnswerMode = Literal["discrete", "probabilities"]


class ConfiguredChatProvider(AsyncOpenAIProvider):
    """The adapter's chat-completions provider, plus the shared parameters and served-by checks."""

    def __init__(self, config: LLMConfig, *, client: openai.AsyncOpenAI | None = None) -> None:
        # Deliberately not calling super().__init__: it would construct its own SDK client.
        self.model_name = config.model
        self.api = "chat_completions"
        self._config = config
        self._client = build_client(client)
        self._shared = shared_request_params(config)
        self.calls: list[dict[str, Any]] = []  # per-call {"payload", "meta"}; read and cleared by the selector

    async def request(self, messages, *, schema: dict[str, Any], structured: bool):
        payload = {
            **self._shared,
            "messages": render_messages(messages),
            "response_format": _response_format(schema, structured=structured),
        }
        record_request(payload, api=self.api)
        # Not inside the adapter's `translating` block: it wraps every non-SDK exception in a plain
        # TypeSafeError, which would turn a FatalRunError into an ordinary per-task error.
        try:
            raw = await self._client.chat.completions.with_raw_response.create(**split_sdk_kwargs(payload))
        except Exception as exc:
            translated = translate_openrouter_error(exc)
            if isinstance(translated, FatalRunError):
                raise translated from exc
            raise self.translate_error(exc) from exc
        body = json.loads(raw.text)
        meta = await check_served(self._config, body, self._client, dict(raw.headers))
        self.calls.append({"payload": json.loads(raw.http_request.content), "meta": meta})
        with translating(self.translate_error):
            return _result(raw.parse())


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
        self._provider = ConfiguredChatProvider(config, client=client)
        self._lock = asyncio.Lock()
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
        async with self._lock:  # provider call records are per-selection
            self._provider.calls.clear()
            try:
                response = await self._adapter.system_one(
                    state=thaw(request.state), questions={QUESTION_ID: question}, model=self._provider
                )
            except Exception as exc:
                translated = translate_typesafe_error(exc)
                if translated is exc:
                    raise
                raise translated from exc
            calls = list(self._provider.calls)

        answer = response.choices[QUESTION_ID]
        payloads = [c["payload"] for c in calls]
        metas = [c["meta"] for c in calls]
        reported = metas[-1]["returned_model"] if metas else None
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
            provider_meta=metas[0] if len(metas) == 1 else {"calls": metas},
        )
