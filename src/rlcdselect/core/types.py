"""Canonical internal types shared by every pipeline.

The rest of the harness depends only on these types, never on MCP SDK or provider SDK classes.
"""

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rlcdselect.core.jsonutil import freeze


@dataclass(frozen=True)
class ToolSpec:
    """One tool as advertised by its provider.

    `input_schema` and `annotations` are deep-frozen; use `jsonutil.thaw` to get plain dicts.
    """

    server_id: str
    name: str
    description: str
    input_schema: Mapping[str, Any]
    annotations: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", freeze(self.input_schema))
        if self.annotations is not None:
            object.__setattr__(self, "annotations", freeze(self.annotations))

    @property
    def key(self) -> str:
        """Stable identity: unique per (server, tool name), independent of presentation."""
        return f"{self.server_id}/{self.name}"


class ToolRole(enum.Enum):
    """Evaluator-only labels. Never shown to a selector or LLM."""

    TRUSTED = "trusted"
    ATTACKER = "attacker"
    DECOY = "decoy"
    IRRELEVANT = "irrelevant"


ABSTAIN = "__abstain__"
"""Outcome label used by metrics for an explicit abstention (no tool selected)."""


@dataclass(frozen=True)
class ExpectedOutcome:
    """Ground truth for one task.

    An empty `tool_keys` means the correct decision is to abstain. `argument_constraints` lists
    argument values that must match exactly; arguments not listed are not scored.
    """

    tool_keys: frozenset[str]
    abstain_reason: str | None = None
    argument_constraints: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_keys", frozenset(self.tool_keys))
        if self.argument_constraints is not None:
            object.__setattr__(self, "argument_constraints", freeze(self.argument_constraints))
        if not self.tool_keys and self.abstain_reason is None:
            raise ValueError("An abstention outcome needs an abstain_reason.")

    @property
    def expects_abstention(self) -> bool:
        return not self.tool_keys


@dataclass(frozen=True)
class Task:
    """A selection task: shared state, its candidate tools, and evaluator-only ground truth."""

    task_id: str
    state: Mapping[str, Any]
    tools: tuple[ToolSpec, ...]
    expected: ExpectedOutcome
    roles: Mapping[str, ToolRole]
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", freeze(self.state))
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "roles", freeze(dict(self.roles)))
        object.__setattr__(self, "tags", tuple(self.tags))
        keys = [t.key for t in self.tools]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Task {self.task_id}: duplicate tool keys {keys}")
        unknown = set(self.expected.tool_keys) - set(keys)
        if unknown:
            raise ValueError(f"Task {self.task_id}: expected tools not in candidate set: {sorted(unknown)}")
        if set(self.roles) != set(keys):
            raise ValueError(f"Task {self.task_id}: every candidate tool needs exactly one role")

    def tool(self, key: str) -> ToolSpec:
        for t in self.tools:
            if t.key == key:
                return t
        raise KeyError(key)


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    extra: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ErrorInfo:
    """A failure, attributed to the pipeline stage where it occurred."""

    stage: str  # "presentation" | "selection" | "arguments" | "execution"
    kind: str
    message: str


@dataclass(frozen=True)
class AttemptLog:
    """One attempt at a model or tool call. Every retry is recorded, never hidden."""

    index: int
    latency_ms: float
    error_kind: str | None = None
    error_message: str | None = None


class SelectionStatus(enum.Enum):
    SELECTED = "selected"
    ABSTAINED = "abstained"
    MULTIPLE = "multiple_tool_calls"  # native arm only: more than one call in a single-choice task
    ERROR = "error"


class ProbabilityKind(enum.Enum):
    """What a selector's probabilities mean. Different kinds are never directly comparable."""

    NONE = "none"
    RLCD_NATIVE = "rlcd_native"  # Jev / Laya readout distribution
    LLM_VERBALIZED = "llm_verbalized"  # numbers an LLM wrote in its output
    LLM_LOGPROB = "llm_logprob"  # derived from token log-probabilities
    MOCK = "mock"


@dataclass(frozen=True)
class SelectionResult:
    status: SelectionStatus
    selected_candidate_id: str | None
    selected_tool_key: str | None
    probabilities: Mapping[str, float] | None  # keyed by candidate id, plus the abstain id
    probability_kind: ProbabilityKind
    probability_issues: tuple[str, ...]  # validation problems; probabilities are never renormalized
    confidence: float | None
    raw_response: Any
    latency_ms: float
    usage: Usage | None
    model_reported: str | None
    error: ErrorInfo | None
    attempts: tuple[AttemptLog, ...]

    @property
    def retry_count(self) -> int:
        return max(0, len(self.attempts) - 1)


class ArgumentStatus(enum.Enum):
    OK = "ok"
    SKIPPED = "skipped"  # nothing to generate: abstained or selection failed
    ERROR = "error"


@dataclass(frozen=True)
class ArgumentResult:
    status: ArgumentStatus
    arguments: Mapping[str, Any] | None
    schema_valid: bool | None
    schema_errors: tuple[str, ...]
    raw_response: Any
    latency_ms: float | None
    usage: Usage | None
    error: ErrorInfo | None
    attempts: tuple[AttemptLog, ...] = ()

    @property
    def retry_count(self) -> int:
        return max(0, len(self.attempts) - 1)


@dataclass(frozen=True)
class ToolExecutionResult:
    success: bool
    output: Any
    error: ErrorInfo | None
    latency_ms: float


@dataclass(frozen=True)
class RetryPolicy:
    """Explicit retry policy. The default makes exactly one attempt.

    Only errors raised as `TransientError` are retried; everything else fails immediately.
    """

    max_attempts: int = 1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")


class TransientError(Exception):
    """A retryable failure such as a timeout, 429, or 5xx. Clients raise it; pipelines retry it."""


class ProviderOutputError(Exception):
    """A model returned output that violates the decision contract. Never retried silently."""

    def __init__(self, kind: str, message: str, raw: Any = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.raw = raw


@dataclass(frozen=True)
class LLMConfig:
    """The single LLM configuration shared by the native arm, the matched selector, and argument generation."""

    provider: str
    model: str
    temperature: float
    max_output_tokens: int = 1024
    seed: int | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "extra", freeze(dict(self.extra)))
