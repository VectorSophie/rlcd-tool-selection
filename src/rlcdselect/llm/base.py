"""Provider-neutral chat/tool-calling interface.

One `ChatClient` instance, with one `LLMConfig`, serves the native arm and the shared argument
generator, and its config is also the matched selector's config. Provider implementations (Phase 2)
must translate `ChatRequest` 1:1 and return the exact provider payload they sent in
`ChatResponse.request_payload`, so the record shows what the model actually received.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from rlcdselect.core.serialization import NativeToolDef
from rlcdselect.core.types import LLMConfig, Usage


@dataclass(frozen=True)
class ForcedTool:
    function_name: str


ToolChoice = Literal["auto"] | ForcedTool


@dataclass(frozen=True)
class ChatRequest:
    system: str
    user: str
    tools: tuple[NativeToolDef, ...]
    tool_choice: ToolChoice
    parallel_tool_calls: bool = False


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any] | None  # None when the raw arguments were not valid JSON
    raw_arguments: str | None


@dataclass(frozen=True)
class ChatResponse:
    tool_calls: tuple[ToolCall, ...]
    text: str | None
    usage: Usage | None
    model_reported: str | None
    raw: Any
    request_payload: Any = None


class ChatClient(Protocol):
    @property
    def config(self) -> LLMConfig: ...

    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Make exactly one provider call. Raise `TransientError` for retryable failures."""
        ...
