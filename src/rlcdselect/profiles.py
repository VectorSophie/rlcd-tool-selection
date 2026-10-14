"""Named experiment profiles and serialization conditions.

Profiles fix the shared LLM configuration. One `LLMConfig` serves native tool calling, matched
selection and argument generation. Conditions fix how decomposed selectors see candidates.
"""

from dataclasses import dataclass

from rlcdselect.core.serialization import CriteriaFormat, NamePolicy, Representation, SerializationConfig
from rlcdselect.core.types import LLMConfig

SHARED_LLM_MODEL = "gpt-5.4-mini-2026-03-17"
JEV_MODEL = "jev-1.13.0"


@dataclass(frozen=True)
class ExperimentProfile:
    name: str
    llm: LLMConfig
    samples_per_condition: int
    purpose: str


DETERMINISTIC_V1 = ExperimentProfile(
    name="deterministic_v1",
    llm=LLMConfig(provider="openai", model=SHARED_LLM_MODEL, temperature=0.0, reasoning_effort="none"),
    samples_per_condition=1,
    purpose="Integration checks and clean discrete outcomes.",
)

STOCHASTIC_V1 = ExperimentProfile(
    name="stochastic_v1",
    llm=LLMConfig(provider="openai", model=SHARED_LLM_MODEL, temperature=0.7, reasoning_effort="none"),
    samples_per_condition=10,
    purpose=(
        "Repeated sampling for empirical selection frequencies. These frequencies are a different "
        "quantity from Jev/Laya native probabilities and are never compared to them directly."
    ),
)

PROFILES = {p.name: p for p in (DETERMINISTIC_V1, STOCHASTIC_V1)}


ARCHITECTURE_MATCHED_V1 = SerializationConfig(
    representation=Representation.NAME_DESCRIPTION_SCHEMA,
    name_policy=NamePolicy.TOOL_NAME,
    criteria_format=CriteriaFormat.OBJECT,
)
"""Main condition: decomposed selectors see name, description and schema, as native calling does."""

ECOLOGICAL_NAME_DESCRIPTION_V1 = SerializationConfig(
    representation=Representation.NAME_DESCRIPTION,
    name_policy=NamePolicy.TOOL_NAME,
    criteria_format=CriteriaFormat.TEXT,
)
"""Documented RLCD routing pattern ("name: description"); not schema-matched to the native arm."""

DUPLICATE_NAME_STRESS_V1 = SerializationConfig(
    representation=Representation.NAME_DESCRIPTION_SCHEMA,
    name_policy=NamePolicy.TOOL_NAME,
    criteria_format=CriteriaFormat.OBJECT,
    allow_duplicate_names=True,
)
"""Decomposed-only stress test with exact duplicate visible names. The runner rejects native arms here."""

CONDITIONS = {
    "architecture_matched_v1": ARCHITECTURE_MATCHED_V1,
    "ecological_name_description_v1": ECOLOGICAL_NAME_DESCRIPTION_V1,
    "duplicate_name_stress_v1": DUPLICATE_NAME_STRESS_V1,
}
