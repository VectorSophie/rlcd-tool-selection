"""Named experiment profiles and serialization conditions.

Profiles fix the shared LLM configuration. One `LLMConfig` serves native tool calling, matched
selection and argument generation. Conditions fix how decomposed selectors see candidates.

Pilot setup (2026-10-14): one OpenRouter account. The shared LLM is Claude Haiku 4.5, served by
Anthropic only, with no fallbacks, every parameter required, and thinking disabled. Jev is
`typesafe/jev-1.13` via OpenRouter's System One API.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from rlcdselect.core.serialization import CriteriaFormat, NamePolicy, Representation, SerializationConfig
from rlcdselect.core.types import LLMConfig, SelectorSamplingPolicy

SHARED_LLM_MODEL = "anthropic/claude-haiku-4.5"
SHARED_LLM_ROUTING = {"only": ["anthropic"], "allow_fallbacks": False, "require_parameters": True}
SHARED_LLM_EXPECTED_PROVIDER = "Anthropic"
# Returned model ids accepted without failing the run. Only the requested id until a live response
# shows what OpenRouter reports. Any other value aborts the run and must be added deliberately.
SHARED_LLM_EXPECTED_RETURNED_MODELS = (SHARED_LLM_MODEL,)

JEV_MODEL = "typesafe/jev-1.13"
JEV_EXPECTED_PROVIDER = "TypeSafe"
JEV_EXPECTED_RETURNED_MODELS = ("typesafe/jev-1.13-20260917",)  # documented in OpenRouter's System One guide

# Jev selector-stability draws per run (selector-only: argument generation runs once, on draw 0).
#   development default = 5   (this profile set; cheap smoke and regression runs)
#   pilot recommendation = 10 (external-dataset pilot; pass --jev-selector-repetitions 10)
#   final N              = chosen from the variance observed on external datasets, not fixed here
DEFAULT_JEV_SELECTOR_REPETITIONS = 5
PILOT_RECOMMENDED_JEV_SELECTOR_REPETITIONS = 10
JEV_EXECUTION_SAMPLE_INDEX = 0  # the first draw drives arguments and execution; never majority vote


def shared_llm(temperature: float) -> LLMConfig:
    return LLMConfig(
        provider="openrouter",
        model=SHARED_LLM_MODEL,
        temperature=temperature,
        thinking="disabled",
        max_output_tokens=1024,
        routing=SHARED_LLM_ROUTING,
        expected_upstream_provider=SHARED_LLM_EXPECTED_PROVIDER,
        expected_returned_models=SHARED_LLM_EXPECTED_RETURNED_MODELS,
    )


@dataclass(frozen=True)
class ExperimentProfile:
    """`samples_per_condition` repeats every arm end to end. `selector_sampling` (by pipeline id)
    repeats only a decomposed arm's selector call, for stability measurement."""

    name: str
    llm: LLMConfig
    samples_per_condition: int
    purpose: str
    selector_sampling: Mapping[str, SelectorSamplingPolicy] = field(default_factory=dict)

    @property
    def jev_selector_repetitions(self) -> int:
        policy = self.selector_sampling.get("jev")
        return policy.repetitions if policy else 1


DETERMINISTIC_V1 = ExperimentProfile(
    # The name is kept for compatibility with pilot records. "Deterministic" refers to the shared
    # LLM only (Claude at temperature 0). Jev exposes no temperature and is not deterministic: the
    # pilot saw identical requests change probabilities by up to ~0.13 and flip act/abstain.
    name="deterministic_v1",
    llm=shared_llm(0.0),
    samples_per_condition=1,
    purpose=(
        "Shared LLM at temperature 0, one end-to-end run per condition. Jev selection is sampled "
        f"{DEFAULT_JEV_SELECTOR_REPETITIONS}x per run (selector-only) because Jev is not deterministic."
    ),
    selector_sampling={"jev": SelectorSamplingPolicy(repetitions=DEFAULT_JEV_SELECTOR_REPETITIONS,
                                                     execution_sample_index=JEV_EXECUTION_SAMPLE_INDEX)},
)

STOCHASTIC_V1 = ExperimentProfile(
    name="stochastic_v1",
    llm=shared_llm(0.7),
    samples_per_condition=10,  # development only; final sample sizes are decided later
    purpose=(
        "Repeated end-to-end sampling for empirical selection frequencies. These frequencies are a "
        "different quantity from Jev/Laya native probabilities and are never compared to them directly. "
        "Every arm, Jev included, is already drawn 10 times, so no extra selector-only draws are made."
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
