import json

from rlcdselect.core.types import Usage
from rlcdselect.llm.base import ChatResponse, ToolCall


def call(name: str, args: dict | None, raw: str | None = None) -> ToolCall:
    return ToolCall(name, args, raw if raw is not None else json.dumps(args))


def response(*calls: ToolCall, text: str | None = None) -> ChatResponse:
    return ChatResponse(tuple(calls), text, Usage(10, 5), "fake-model", raw={"scripted": True})
