"""Deterministic offline stand-ins for an LLM. Their decisions are not a model's; they exist to test wiring.

`KeywordChatClient` scores tools by word overlap with the request and fills arguments with simple
heuristics. `KeywordSelector` (in `selectors.mock`) uses the same scorer, so offline runs of the native
and decomposed arms are driven by one shared fake "model".
"""

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from rlcdselect.core.types import LLMConfig, Usage
from rlcdselect.llm.base import ChatRequest, ChatResponse, ForcedTool, ToolCall

_STOPWORDS = frozenset(
    "the a an and or for to of in on at by with from into this that these those is are be it its "
    "my me i you your our we us can could would should please about any some all one".split()
)
_WORD_RE = re.compile(r"[a-z0-9]+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_INT_RE = re.compile(r"\b\d+\b")
_QUOTED_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")

FAKE_CONFIG = LLMConfig(provider="fake", model="keyword-v1", temperature=0.0)


def tokens(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower().replace("_", " ").replace("-", " "))
    return {w.rstrip("s") for w in words if len(w) > 2 and w not in _STOPWORDS}


def strings_in(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for v in value.values() for s in strings_in(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in strings_in(v)]
    return []


def request_text(user_content: str) -> str:
    try:
        return " ".join(strings_in(json.loads(user_content)))
    except json.JSONDecodeError:
        return user_content


def best_match(request: str, options: Sequence[tuple[str, str]], threshold: int) -> tuple[str | None, dict[str, int]]:
    """Return the option key with the most word overlap, or None below `threshold`.

    Ties go to the earliest option, which makes the fake order-sensitive just as real models can be.
    """
    req = tokens(request)
    scores = {key: len(req & tokens(text)) for key, text in options}
    best_key, best = None, -1
    for key, _ in options:
        if scores[key] > best:
            best_key, best = key, scores[key]
    return (best_key if best >= threshold else None), scores


def fill_arguments(parameters: Mapping[str, Any], text: str) -> dict[str, Any]:
    """Fill required properties from the request text with crude heuristics."""
    props = parameters.get("properties", {})
    args: dict[str, Any] = {}
    quoted = [a or b for a, b in _QUOTED_RE.findall(text)]
    dates = _DATE_RE.findall(text)
    date_fields = 0
    for name in parameters.get("required", []):
        schema = props.get(name, {})
        kind = schema.get("type")
        if kind == "array":
            args[name] = _EMAIL_RE.findall(text) or [text]
        elif kind == "integer":
            ints = _INT_RE.findall(text)
            args[name] = int(ints[0]) if ints else 1
        elif kind == "number":
            ints = _INT_RE.findall(text)
            args[name] = float(ints[0]) if ints else 1.0
        elif kind == "boolean":
            args[name] = False
        elif schema.get("format") == "date" or "date" in name:
            args[name] = dates[min(date_fields, len(dates) - 1)] if dates else ""
            date_fields += 1
        elif "subject" in name and quoted:
            args[name] = quoted[0]
        else:
            args[name] = text
    return args


class KeywordChatClient:
    """Fake tool-calling LLM: picks the best-overlapping tool, or answers in text below threshold."""

    def __init__(self, config: LLMConfig = FAKE_CONFIG, threshold: int = 2) -> None:
        self._config = config
        self.threshold = threshold
        self.requests: list[ChatRequest] = []

    @property
    def config(self) -> LLMConfig:
        return self._config

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        text = request_text(request.user)
        if isinstance(request.tool_choice, ForcedTool):
            target = next(t for t in request.tools if t.function_name == request.tool_choice.function_name)
        else:
            options = [(t.function_name, f"{t.function_name} {t.description}") for t in request.tools]
            chosen, _ = best_match(text, options, self.threshold)
            if chosen is None:
                return ChatResponse((), "No suitable tool.", Usage(0, 0), self._config.model, raw={"fake": True})
            target = next(t for t in request.tools if t.function_name == chosen)
        args = fill_arguments(target.parameters, text)
        call = ToolCall(name=target.function_name, arguments=args, raw_arguments=json.dumps(args))
        return ChatResponse((call,), None, Usage(0, 0), self._config.model, raw={"fake": True})


ScriptStep = ChatResponse | Exception | Callable[[ChatRequest], ChatResponse]


class ScriptedChatClient:
    """Returns (or raises) scripted steps in order. Records every request for assertions."""

    def __init__(self, steps: Iterable[ScriptStep], config: LLMConfig = FAKE_CONFIG) -> None:
        self._steps = list(steps)
        self._config = config
        self.requests: list[ChatRequest] = []

    @property
    def config(self) -> LLMConfig:
        return self._config

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        if not self._steps:
            raise AssertionError("ScriptedChatClient ran out of scripted steps")
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        if callable(step):
            return step(request)
        return step
