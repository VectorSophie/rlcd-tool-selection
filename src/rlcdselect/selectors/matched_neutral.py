"""Matched-neutral selector: the shared Claude model makes the same discrete choice as the other
decomposed selectors, through a minimal project-owned prompt instead of the System One adapter.

It is the control for the architecture comparison. Against the native arm, the only intended
difference is that selection is a separate discrete-choice call and arguments are generated
afterwards by the shared argument generator. Against `matched_systemone`, the only intended
difference is the selector framing:

- the same `SelectorRequest` (candidate ids, presentation order, criteria, `none` option);
- option lines rendered by `serialization.choice_lines`, byte-identical to the adapter's;
- the same model, provider routing, temperature, max tokens, thinking setting and served-by checks
  (`shared_request_params`, `check_served`), from the same `LLMConfig` as the native arm;
- no "untrusted document" wrapper, no security warning and no routing language
  (`prompts.NEUTRAL_SELECTOR_PROMPT`, versioned).

The answer is a strict JSON schema `{"choice": <one option id>}`. No corrective retries: a malformed
answer is a recorded selector error, and transient retries are the pipeline's, as for every arm.
"""

import json
from typing import Any

import openai

from rlcdselect.core.prompts import NEUTRAL_SELECTOR_PROMPT, NEUTRAL_SELECTOR_PROMPT_VERSION
from rlcdselect.core.serialization import SelectorRequest, choice_lines, render_state
from rlcdselect.core.types import LLMConfig, ProbabilityKind, ProviderOutputError
from rlcdselect.llm.openrouter import (
    build_client,
    check_served,
    parse_chat_completion,
    shared_request_params,
    split_sdk_kwargs,
    translate_openrouter_error,
)
from rlcdselect.selectors.base import SelectorOutput

SELECTOR_ID = "matched_neutral"


def neutral_user_message(request: SelectorRequest) -> str:
    return render_state(request.state) + "\n\nOptions:\n" + "\n".join(choice_lines(request))


def neutral_response_format(request: SelectorRequest) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": "choice", "strict": True, "schema": {
        "type": "object",
        "properties": {"choice": {"type": "string", "enum": list(request.option_ids)}},
        "required": ["choice"],
        "additionalProperties": False,
    }}}


class MatchedNeutralSelector:
    def __init__(self, config: LLMConfig, *, client: openai.AsyncOpenAI | None = None) -> None:
        shared_request_params(config)  # validate eagerly
        self._config = config
        self._client = build_client(client)

    @property
    def selector_id(self) -> str:
        return SELECTOR_ID

    @property
    def model(self) -> str:
        return f"{self._config.provider}/{self._config.model}"

    @property
    def probability_kind(self) -> ProbabilityKind:
        return ProbabilityKind.NONE

    @property
    def llm_config(self) -> LLMConfig:
        return self._config

    @property
    def prompt_version(self) -> str:
        return NEUTRAL_SELECTOR_PROMPT_VERSION

    def build_payload(self, request: SelectorRequest) -> dict[str, Any]:
        return {
            **shared_request_params(self._config),
            "messages": [{"role": "system", "content": NEUTRAL_SELECTOR_PROMPT},
                         {"role": "user", "content": neutral_user_message(request)}],
            "response_format": neutral_response_format(request),
        }

    async def select(self, request: SelectorRequest) -> SelectorOutput:
        payload = self.build_payload(request)
        try:
            raw = await self._client.chat.completions.with_raw_response.create(**split_sdk_kwargs(payload))
        except Exception as exc:
            translated = translate_openrouter_error(exc)
            if translated is exc:
                raise
            raise translated from exc
        sent = json.loads(raw.http_request.content)
        body = json.loads(raw.text)
        meta = await check_served(self._config, body, self._client, dict(raw.headers))
        response = parse_chat_completion(body, sent, meta)
        try:
            choice = json.loads(response.text or "")["choice"]
            if not isinstance(choice, str):
                raise TypeError(type(choice).__name__)
        except (ValueError, KeyError, TypeError) as exc:
            # Served and billed, so the metadata is kept for the budget guard.
            raise ProviderOutputError("malformed_output", f"No structured choice in the answer: {exc}",
                                      raw=body, provider_meta=meta) from exc
        return SelectorOutput(
            choice=choice, probabilities=None, confidence=None, usage=response.usage,
            model_reported=response.model_reported,
            raw={"answer": {"choice": choice}, "text": response.text, "prompt_version": NEUTRAL_SELECTOR_PROMPT_VERSION},
            request_payload=sent, provider_meta=meta,
        )

