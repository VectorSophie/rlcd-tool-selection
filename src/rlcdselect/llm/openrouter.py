"""OpenRouter-backed Claude client: the shared LLM for native tool calling, matched selection and
argument generation.

`shared_request_params(config)` is the single source of model, temperature, max_tokens, thinking and
provider-routing settings. Both this client and the matched-LLM adapter provider apply it, and a
payload test asserts the three roles send identical values.

Every response is checked, and these conditions abort the run with `FatalRunError`:
- the request was served by a provider other than `config.expected_upstream_provider`;
- the returned model id is not in `config.expected_returned_models`;
- OpenRouter could not route the request (404), e.g. because a required parameter is unsupported
  by the allowed provider (`require_parameters: true`);
- thinking was configured disabled but reasoning tokens were used.

The upstream provider is read from the response's `provider` field. If that field is absent, it
is looked up through `GET /api/v1/generation?id=...`, and the record says which source was used.

`parallel_tool_calls` is never sent: the Anthropic endpoint does not list it as supported, and
with `require_parameters: true` it would make every request unroutable.
"""

import asyncio
import json
import os
from typing import Any

import httpx2
import openai

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import FatalRunError, LLMConfig, ProviderError, ProviderOutputError, TransientError, Usage
from rlcdselect.llm.base import ChatRequest, ChatResponse, ForcedTool, ToolCall

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_TRANSIENT_STATUS = {408, 409, 429}
_HEADER_KEYS = ("x-request-id", "x-generation-id", "openrouter-request-id", "cf-ray")


def shared_request_params(config: LLMConfig) -> dict[str, Any]:
    """Model, sampling, thinking and routing parameters common to every shared-LLM call."""
    if config.provider != "openrouter":
        raise ValueError(f"OpenRouter client got provider {config.provider!r}")
    if config.seed is not None:
        raise ValueError("LLMConfig.seed is not supported for this client")
    if config.reasoning_effort is not None:
        raise ValueError("Use LLMConfig.thinking, not reasoning_effort, for this client")
    params: dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
    }
    if config.thinking == "disabled":
        params["reasoning"] = {"enabled": False}
    elif config.thinking is not None:
        raise ValueError(f"Unsupported thinking setting {config.thinking!r}")
    if config.routing is not None:
        params["provider"] = thaw(config.routing)
    params.update(thaw(config.extra))
    return params


def build_client(client: openai.AsyncOpenAI | None = None) -> openai.AsyncOpenAI:
    if client is None:
        # Explicit key: the SDK would otherwise read OPENAI_API_KEY.
        return openai.AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ.get("OPENROUTER_API_KEY"),
                                  max_retries=0)
    if client.max_retries != 0:
        raise ValueError("Pass an AsyncOpenAI client with max_retries=0; retries are owned by the harness")
    return client


def split_sdk_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """OpenRouter-only fields go through `extra_body`; everything else is a named SDK argument."""
    kwargs = {k: v for k, v in payload.items() if k not in ("provider", "reasoning")}
    extra = {k: payload[k] for k in ("provider", "reasoning") if k in payload}
    if extra:
        kwargs["extra_body"] = extra
    return kwargs


def translate_openrouter_error(exc: Exception) -> Exception:
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return TransientError(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, openai.APIStatusError):
        body = getattr(exc, "body", None)
        if exc.status_code == 404:
            return FatalRunError("routing_rejected", f"OpenRouter could not route the request: {exc}", raw=body)
        if exc.status_code in _TRANSIENT_STATUS or exc.status_code >= 500:
            return TransientError(f"HTTP {exc.status_code}: {exc}")
        return ProviderError(f"http_{exc.status_code}", str(exc), raw=body)
    return exc


async def lookup_generation(client: openai.AsyncOpenAI, generation_id: str, attempts: int = 5,
                            delay_s: float = 0.5) -> dict[str, Any] | None:
    """Fetch OpenRouter's generation record. Stats can lag the response briefly, so 404 is retried."""
    http = client._client  # the SDK's underlying httpx2 client (keeps transport injection working in tests)
    url = f"{str(client.base_url).rstrip('/')}/generation"
    headers = {"Authorization": f"Bearer {client.api_key}"}
    for i in range(attempts):
        resp = await http.get(url, params={"id": generation_id}, headers=headers)
        if resp.status_code == 200:
            return resp.json().get("data")
        if resp.status_code != 404:
            return None
        await asyncio.sleep(delay_s * (i + 1))
    return None


async def check_served(config: LLMConfig, body: dict[str, Any], client: openai.AsyncOpenAI,
                       headers: dict[str, str]) -> dict[str, Any]:
    """Validate provider, model and thinking for one response; return the provider metadata to log."""
    generation_id = body.get("id")
    provider, source, request_id = body.get("provider"), "response", None
    if provider is None and generation_id:
        record = await lookup_generation(client, generation_id)
        if record:
            provider, source, request_id = record.get("provider_name"), "generation_api", record.get("request_id")
    usage = body.get("usage") or {}
    reasoning_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    meta = {
        "gateway": "openrouter",
        "requested_model": config.model,
        "returned_model": body.get("model"),
        "provider": provider,
        "provider_source": source if provider is not None else None,
        "generation_id": generation_id,
        "request_id": request_id,
        "response_headers": {k: v for k, v in headers.items() if k.lower() in _HEADER_KEYS},
        "temperature": config.temperature,
        "thinking": config.thinking,
        "routing": thaw(config.routing),
        "reasoning_tokens": reasoning_tokens,
        "cost": usage.get("cost"),
    }
    if config.expected_upstream_provider is not None and provider != config.expected_upstream_provider:
        raise FatalRunError("provider_mismatch",
                            f"Expected upstream provider {config.expected_upstream_provider!r}, got {provider!r}", raw=meta)
    if config.expected_returned_models and body.get("model") not in config.expected_returned_models:
        raise FatalRunError("model_mismatch",
                            f"Returned model {body.get('model')!r} not in expected {list(config.expected_returned_models)}",
                            raw=meta)
    if config.thinking == "disabled" and reasoning_tokens:
        raise FatalRunError("thinking_not_disabled", f"Thinking disabled but {reasoning_tokens} reasoning tokens used",
                            raw=meta)
    return meta


class OpenRouterChatClient:
    def __init__(self, config: LLMConfig, *, client: openai.AsyncOpenAI | None = None) -> None:
        shared_request_params(config)  # validate eagerly
        self._config = config
        self._client = build_client(client)

    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def sdk_client(self) -> openai.AsyncOpenAI:
        return self._client

    def build_payload(self, request: ChatRequest) -> dict[str, Any]:
        tools = [
            {"type": "function", "function": {"name": t.function_name, "description": t.description,
                                              "parameters": thaw(t.parameters)}}
            for t in request.tools
        ]
        if isinstance(request.tool_choice, ForcedTool):
            tool_choice: Any = {"type": "function", "function": {"name": request.tool_choice.function_name}}
        else:
            tool_choice = request.tool_choice
        # request.parallel_tool_calls is deliberately not sent (see module docstring); multiple calls
        # are detected and recorded by the pipelines instead.
        return {
            **shared_request_params(self._config),
            "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": request.user}],
            "tools": tools,
            "tool_choice": tool_choice,
        }

    async def complete(self, request: ChatRequest) -> ChatResponse:
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
        return parse_chat_completion(body, sent, meta)

    async def aclose(self) -> None:
        await self._client.close()


def parse_chat_completion(body: dict[str, Any], sent: dict[str, Any], meta: dict[str, Any]) -> ChatResponse:
    choices = body.get("choices") or []
    if len(choices) != 1:
        raise ProviderOutputError("malformed_output", f"Expected 1 choice, got {len(choices)}", raw=body, provider_meta=meta)
    choice = choices[0]
    if choice.get("finish_reason") not in ("stop", "tool_calls", None):
        raise ProviderOutputError("incomplete_response", f"finish_reason={choice.get('finish_reason')!r}", raw=body, provider_meta=meta)
    message = choice.get("message") or {}
    if message.get("refusal"):
        raise ProviderOutputError("refusal", str(message["refusal"]), raw=body, provider_meta=meta)
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        raw_args = fn.get("arguments")
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = None
        calls.append(ToolCall(fn.get("name"), args if isinstance(args, dict) else None, raw_args))
    u = body.get("usage") or {}
    usage = Usage(
        input_tokens=u.get("prompt_tokens"),
        output_tokens=u.get("completion_tokens"),
        extra={"cost": u.get("cost"),
               "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
               "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")},
    )
    return ChatResponse(
        tool_calls=tuple(calls), text=message.get("content") or None, usage=usage,
        model_reported=body.get("model"), raw=body, request_payload=sent, provider_meta=meta,
    )


class ModelUnavailableError(RuntimeError):
    """A pinned model, provider endpoint or parameter is not available. Nothing is substituted."""


class OpenRouterCatalog:
    """Free startup checks against OpenRouter's public model-endpoint listing."""

    def __init__(self, http: httpx2.AsyncClient | None = None, base_url: str = OPENROUTER_BASE_URL) -> None:
        self._http = http or httpx2.AsyncClient(timeout=30)
        self._base = base_url.rstrip("/")

    async def endpoints(self, model: str) -> list[dict[str, Any]]:
        resp = await self._http.get(f"{self._base}/models/{model}/endpoints")
        if resp.status_code != 200:
            raise ModelUnavailableError(f"OpenRouter has no model {model!r} (HTTP {resp.status_code})")
        return resp.json()["data"].get("endpoints", [])

    async def verify(self, model: str, provider_name: str, required_params: list[str] = (),
                     tag: str | None = None) -> dict[str, Any]:
        """Require an endpoint from `provider_name` (and routing slug `tag`, if given) that supports
        every parameter in `required_params`."""
        endpoints = await self.endpoints(model)
        matching = [e for e in endpoints
                    if e.get("provider_name") == provider_name and (tag is None or e.get("tag") == tag)]
        if not matching:
            raise ModelUnavailableError(
                f"No {provider_name!r} endpoint for {model!r}; available providers: "
                f"{sorted({e.get('provider_name') for e in endpoints})}")
        best = None
        for e in matching:
            supported = set(e.get("supported_parameters") or [])
            missing = [p for p in required_params if p not in supported]
            if not missing:
                best = e
                break
        if best is None:
            raise ModelUnavailableError(
                f"{provider_name!r} endpoint for {model!r} does not support {missing}; "
                f"supported: {sorted(set(matching[0].get('supported_parameters') or []))}")
        return {"model": model, "provider": provider_name, "tag": best.get("tag"),
                "supported_parameters": best.get("supported_parameters"), "pricing": best.get("pricing")}

    async def aclose(self) -> None:
        await self._http.aclose()


SHARED_LLM_REQUIRED_PARAMETERS = [
    "temperature", "max_tokens", "reasoning",  # every call
    "tools", "tool_choice",  # native arm and argument generation
    "response_format", "structured_outputs",  # matched selector (strict JSON schema)
]
