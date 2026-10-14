"""OpenAI Responses API client: the shared LLM for native tool calling and argument generation.

`shared_request_params` is the single source of the model and sampling parameters. The matched-LLM
selector's provider (`selectors.matched_llm`) applies the same function, so all three LLM roles send
identical model, temperature, reasoning and output-limit settings.

The SDK client is constructed with `max_retries=0`, because retries belong to the harness, where
they are logged.
"""

import copy
import json
from typing import Any

import openai

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import LLMConfig, ProviderError, ProviderOutputError, TransientError, Usage
from rlcdselect.llm.base import ChatRequest, ChatResponse, ForcedTool, ToolCall

_TRANSIENT_STATUS = {408, 409, 429}


def shared_request_params(config: LLMConfig) -> dict[str, Any]:
    if config.provider != "openai":
        raise ValueError(f"OpenAI client got provider {config.provider!r}")
    if config.seed is not None:
        raise ValueError("The Responses API has no seed parameter; LLMConfig.seed must be None")
    params: dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "max_output_tokens": config.max_output_tokens,
        "store": False,
    }
    if config.reasoning_effort is not None:
        params["reasoning"] = {"effort": config.reasoning_effort}
    params.update(thaw(config.extra))
    return params


def build_client(client: openai.AsyncOpenAI | None = None) -> openai.AsyncOpenAI:
    if client is None:
        return openai.AsyncOpenAI(max_retries=0)
    if client.max_retries != 0:
        raise ValueError("Pass an AsyncOpenAI client with max_retries=0; retries are owned by the harness")
    return client


def translate_openai_error(exc: Exception) -> Exception:
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return TransientError(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code in _TRANSIENT_STATUS or exc.status_code >= 500:
            return TransientError(f"HTTP {exc.status_code}: {exc}")
        return ProviderError(f"http_{exc.status_code}", str(exc), raw=getattr(exc, "body", None))
    return exc


class OpenAIResponsesClient:
    def __init__(self, config: LLMConfig, *, client: openai.AsyncOpenAI | None = None, strict_tools: bool = False) -> None:
        shared_request_params(config)  # validate eagerly
        self._config = config
        self._client = build_client(client)
        self.strict_tools = strict_tools

    @property
    def config(self) -> LLMConfig:
        return self._config

    def build_payload(self, request: ChatRequest) -> dict[str, Any]:
        """The exact keyword arguments passed to `responses.create`."""
        tools = [
            {
                "type": "function",
                "name": t.function_name,
                "description": t.description,
                "parameters": thaw(t.parameters),
                "strict": self.strict_tools,
            }
            for t in request.tools
        ]
        if isinstance(request.tool_choice, ForcedTool):
            tool_choice: Any = {"type": "function", "name": request.tool_choice.function_name}
        else:
            tool_choice = request.tool_choice
        return {
            **shared_request_params(self._config),
            "instructions": request.system,
            "input": [{"role": "user", "content": request.user}],
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": request.parallel_tool_calls,
        }

    async def complete(self, request: ChatRequest) -> ChatResponse:
        payload = self.build_payload(request)
        try:
            response = await self._client.responses.create(**copy.deepcopy(payload))
        except Exception as exc:
            translated = translate_openai_error(exc)
            if translated is exc:
                raise
            raise translated from exc
        if response.model != self._config.model:
            raise ProviderError("model_mismatch",
                                f"Requested {self._config.model!r} but the response reports {response.model!r}",
                                raw=response.model_dump(mode="json"))
        return parse_response(response, payload)

    async def verify_model_available(self) -> None:
        """Fail if the configured model id is not available to this account."""
        try:
            await self._client.models.retrieve(self._config.model)
        except openai.NotFoundError as exc:
            raise ModelUnavailableError(f"OpenAI model {self._config.model!r} is not available: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.close()


class ModelUnavailableError(RuntimeError):
    """A pinned model id is not available. The harness never substitutes another model."""


def parse_response(response: Any, payload: dict[str, Any]) -> ChatResponse:
    raw = response.model_dump(mode="json")
    if response.status != "completed":
        reason = response.error.message if response.error else (
            response.incomplete_details.reason if response.incomplete_details else response.status)
        raise ProviderOutputError("incomplete_response", f"Response status {response.status}: {reason}", raw=raw)
    calls: list[ToolCall] = []
    texts: list[str] = []
    for item in response.output:
        if item.type == "function_call":
            try:
                args = json.loads(item.arguments)
            except json.JSONDecodeError:
                args = None
            calls.append(ToolCall(item.name, args if isinstance(args, dict) else None, item.arguments))
        elif item.type == "message":
            for part in item.content:
                if part.type == "refusal":
                    raise ProviderOutputError("refusal", part.refusal, raw=raw)
                if part.type == "output_text":
                    texts.append(part.text)
    usage = None
    if response.usage is not None:
        u = response.usage
        usage = Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            extra={
                "cached_input_tokens": getattr(u.input_tokens_details, "cached_tokens", None),
                "reasoning_tokens": getattr(u.output_tokens_details, "reasoning_tokens", None),
            },
        )
    return ChatResponse(
        tool_calls=tuple(calls),
        text="".join(texts) if texts else None,
        usage=usage,
        model_reported=response.model,
        raw=raw,
        request_payload=payload,
    )
