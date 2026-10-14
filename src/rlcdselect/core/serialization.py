"""Candidate presentation and serialization: the single path by which any arm sees tools.

Every arm, native or decomposed, gets its view of the candidate set from this module:

1. `present_candidates` fixes the presentation order and assigns opaque candidate ids. Both are
   seeded and deterministic. Ids are independent of presentation order, so an order shuffle
   changes position without also changing labels.
2. `build_selector_request` builds the Choice-style request that every decomposed selector
   receives (LLM via System One adapter, Jev, Laya, mocks), so they all see identical criteria.
3. `build_native_tools` builds the function definitions for native tool calling and for the
   shared argument generator.

The real tool name stays visible to selectors as metadata in the criteria text. The opaque id is
only the answer key.
"""

import enum
import json
import random
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import Task, ToolSpec


class Representation(enum.Enum):
    NAME_ONLY = "name_only"
    NAME_DESCRIPTION = "name_description"
    NAME_DESCRIPTION_SCHEMA = "name_description_schema"


class NamePolicy(enum.Enum):
    """How a tool's selector-visible name is derived. The same name is used by every arm."""

    TOOL_NAME = "tool_name"  # the raw tool name; duplicate names are an error
    SERVER_QUALIFIED = "server_qualified"  # always "<server_id>__<name>"
    QUALIFY_ON_COLLISION = "qualify_on_collision"  # qualify only names that collide


class CriteriaFormat(enum.Enum):
    TEXT = "text"  # "name: description" strings (Jev/Laya documented routing pattern)
    OBJECT = "object"  # {"name": ..., "description": ..., "input_schema": ...}


ABSTAIN_ID = "none"
ABSTAIN_CRITERION = (
    "None of these tools: no listed tool fits the request, or the request lacks information "
    "that the tool would need."
)
SELECTION_INSTRUCTIONS = "Which tool should handle the user's request?"

# Function names accepted by the major tool-calling APIs. Names that violate this are rejected,
# never silently rewritten, because a rewrite would change what the model sees.
_FUNCTION_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_QUALIFIER = "__"


class SerializationError(ValueError):
    """The candidate set cannot be presented under the requested configuration."""


@dataclass(frozen=True)
class SerializationConfig:
    representation: Representation = Representation.NAME_DESCRIPTION
    name_policy: NamePolicy = NamePolicy.TOOL_NAME
    criteria_format: CriteriaFormat = CriteriaFormat.TEXT
    include_abstain: bool = True
    # Only for the decomposed-only exact-duplicate-name stress test. Native function calling cannot
    # represent duplicate names, so the runner refuses to pair this with a native arm.
    allow_duplicate_names: bool = False


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    display_name: str
    tool: ToolSpec


@dataclass(frozen=True)
class CandidateSet:
    """Candidates in presentation order, plus the seeds that produced the order and ids."""

    candidates: tuple[Candidate, ...]
    order_seed: int | None
    id_seed: int | None

    def by_id(self, candidate_id: str) -> Candidate:
        for c in self.candidates:
            if c.candidate_id == candidate_id:
                return c
        raise KeyError(candidate_id)

    def by_display_name(self, display_name: str) -> Candidate:
        for c in self.candidates:
            if c.display_name == display_name:
                return c
        raise KeyError(display_name)

    @property
    def tool_order(self) -> tuple[str, ...]:
        return tuple(c.tool.key for c in self.candidates)

    @property
    def id_map(self) -> dict[str, str]:
        return {c.candidate_id: c.tool.key for c in self.candidates}


def _display_names(tools: Sequence[ToolSpec], policy: NamePolicy, *, allow_duplicates: bool = False) -> list[str]:
    counts = Counter(t.name for t in tools)
    names = []
    for t in tools:
        qualified = f"{t.server_id}{_QUALIFIER}{t.name}"
        if policy is NamePolicy.SERVER_QUALIFIED:
            names.append(qualified)
        elif policy is NamePolicy.QUALIFY_ON_COLLISION:
            names.append(qualified if counts[t.name] > 1 else t.name)
        else:
            names.append(t.name)
    duplicates = sorted(n for n, c in Counter(names).items() if c > 1)
    if duplicates and not allow_duplicates:
        raise SerializationError(
            f"Duplicate selector-visible names {duplicates} under name policy {policy.value!r}; "
            "use server_qualified or qualify_on_collision."
        )
    return names


def present_candidates(
    tools: Sequence[ToolSpec],
    *,
    name_policy: NamePolicy,
    order_seed: int | None = None,
    id_seed: int | None = None,
    allow_duplicate_names: bool = False,
) -> CandidateSet:
    """Assign opaque ids and a presentation order.

    Ids are `t0..t{n-1}`. With `id_seed=None`, a tool's id is its index in the canonical tool
    tuple; otherwise ids are a seeded permutation. The presentation order is the canonical order
    when `order_seed` is None, otherwise a seeded shuffle. The two seeds are independent factors.
    """
    tools = tuple(tools)
    names = _display_names(tools, name_policy, allow_duplicates=allow_duplicate_names)
    n = len(tools)
    id_index = list(range(n))
    if id_seed is not None:
        random.Random(id_seed).shuffle(id_index)
    order = list(range(n))
    if order_seed is not None:
        random.Random(order_seed).shuffle(order)
    candidates = tuple(
        Candidate(candidate_id=f"t{id_index[i]}", display_name=names[i], tool=tools[i]) for i in order
    )
    return CandidateSet(candidates=candidates, order_seed=order_seed, id_seed=id_seed)


def present_task(task: Task, config: SerializationConfig, *, order_seed: int | None, id_seed: int | None) -> CandidateSet:
    return present_candidates(task.tools, name_policy=config.name_policy, order_seed=order_seed, id_seed=id_seed,
                              allow_duplicate_names=config.allow_duplicate_names)


def criterion_for(candidate: Candidate, config: SerializationConfig) -> str | dict[str, Any]:
    """The exact selector-visible description of one candidate."""
    tool = candidate.tool
    rep = config.representation
    if config.criteria_format is CriteriaFormat.OBJECT:
        obj: dict[str, Any] = {"name": candidate.display_name}
        if rep is not Representation.NAME_ONLY:
            obj["description"] = tool.description
        if rep is Representation.NAME_DESCRIPTION_SCHEMA:
            obj["input_schema"] = thaw(tool.input_schema)
        return obj
    if rep is Representation.NAME_ONLY:
        return candidate.display_name
    text = f"{candidate.display_name}: {tool.description}" if tool.description else candidate.display_name
    if rep is Representation.NAME_DESCRIPTION_SCHEMA:
        # Original property order, matching what the native arm and argument generator receive.
        text += f"\nInput schema: {json.dumps(thaw(tool.input_schema), separators=(',', ':'), ensure_ascii=False)}"
    return text


@dataclass(frozen=True)
class SelectorRequest:
    """What every decomposed selector receives. Selectors must not build their own view of tools."""

    state: Mapping[str, Any]
    instructions: str
    criteria: Mapping[str, Any]  # candidate id -> criterion, in presentation order, then abstain
    candidate_ids: tuple[str, ...]
    abstain_id: str | None
    config: SerializationConfig

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(self.criteria)


def build_selector_request(state: Mapping[str, Any], cset: CandidateSet, config: SerializationConfig) -> SelectorRequest:
    criteria: dict[str, Any] = {c.candidate_id: criterion_for(c, config) for c in cset.candidates}
    if ABSTAIN_ID in criteria:
        raise SerializationError(f"Candidate id collides with the abstain id {ABSTAIN_ID!r}")
    abstain_id = None
    if config.include_abstain:
        criteria[ABSTAIN_ID] = ABSTAIN_CRITERION
        abstain_id = ABSTAIN_ID
    return SelectorRequest(
        state=thaw(state),
        instructions=SELECTION_INSTRUCTIONS,
        criteria=criteria,
        candidate_ids=tuple(c.candidate_id for c in cset.candidates),
        abstain_id=abstain_id,
        config=config,
    )


@dataclass(frozen=True)
class NativeToolDef:
    """A provider-neutral function definition. Provider adapters translate it 1:1 and must log the result."""

    function_name: str
    description: str
    parameters: Mapping[str, Any]
    candidate_id: str


def native_tool_def(candidate: Candidate) -> NativeToolDef:
    if not _FUNCTION_NAME_RE.match(candidate.display_name):
        raise SerializationError(
            f"Tool name {candidate.display_name!r} is not a valid function name for native tool calling"
        )
    return NativeToolDef(
        function_name=candidate.display_name,
        description=candidate.tool.description,
        parameters=thaw(candidate.tool.input_schema),
        candidate_id=candidate.candidate_id,
    )


def build_native_tools(cset: CandidateSet) -> tuple[NativeToolDef, ...]:
    """All candidates as function definitions, in presentation order.

    Native tool calling always exposes description and schema. That is inherent to the arm and is
    logged as such; the decomposed arms' representation is configured separately.
    """
    defs = tuple(native_tool_def(c) for c in cset.candidates)
    duplicates = sorted(n for n, c in Counter(d.function_name for d in defs).items() if c > 1)
    if duplicates:
        raise SerializationError(f"Native function calling cannot represent duplicate function names {duplicates}")
    return defs


def render_state(state: Mapping[str, Any]) -> str:
    """The state as chat models receive it: compact JSON in the state's own key order, as Jev receives it."""
    return json.dumps(thaw(state), separators=(",", ":"), ensure_ascii=False)
