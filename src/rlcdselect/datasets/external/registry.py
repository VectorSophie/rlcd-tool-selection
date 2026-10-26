"""Named external datasets for the runner: what each name loads, which items are eligible, which
serialization condition it runs under, and how it is sampled.

Roles:
- `primary`: may enter primary pilot metrics.
- `sanity_only`: tiny or weakly labelled; reported separately, never in a headline aggregate.
- `diagnostic`: items excluded from primary results for data-quality reasons, kept as their own
  subsets so they can be inspected or run separately.

Primary BFCL subsets exclude every item flagged by the adapter as `gold_schema_inconsistent`,
`gold_contains_placeholder` (gold accepts a literal "N/A") or `gold_empty_alternative` (an
undocumented `[]` accepted-value list). Those items form the diagnostic subsets
`bfcl_schema_inconsistent`, `bfcl_na_gold` and `bfcl_ambiguous_empty_alternative`; an item with
several flags appears in each matching subset with every reason recorded.

Conditions: datasets with source schemas (When2Call, BFCL) run under `architecture_matched_v1`.
MetaTool has no schemas, so it runs under `ecological_name_description_v1` (name + description).
No schema is invented to fit the main condition, and the condition is recorded per dataset, so
MetaTool is never silently pooled with schema-bearing tasks.

Sampling is deterministic: eligible items are sorted by task id, and each stratum is sampled with
`random.Random(f"{seed}:{dataset}:{stratum}")`. A stratum smaller than requested is an error,
never a silent shrink. Each sampled task gets its own presentation-order seed derived from the
sampling seed and its task id (`task_order_seed`).
"""

import hashlib
import random
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from rlcdselect.core.types import Task
from rlcdselect.datasets.external import bfcl, metatool, when2call
from rlcdselect.datasets.external.common import AdapterResult

QUALITY_FLAGS = {
    "gold_schema_inconsistent": "bfcl_schema_inconsistent",
    "gold_contains_placeholder": "bfcl_na_gold",
    "gold_empty_alternative": "bfcl_ambiguous_empty_alternative",
}
BFCL_ANSWERED = ("simple_python", "multiple", "live_simple", "live_multiple")


class SamplingError(ValueError):
    pass


def _clean(task: Task) -> bool:
    return not any(flag in task.tags for flag in QUALITY_FLAGS)


def _label(task: Task) -> str:
    return str((task.provenance or {}).get("source_label"))


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    role: str  # primary | sanity_only | diagnostic
    condition: str
    sources: tuple[str, ...]  # adapter loads, e.g. ("bfcl", "live_simple")
    include: Callable[[Task], bool] = lambda t: True
    default_sample_size: int = 100
    strata: Mapping[str, int] | None = None  # source_label -> count, when stratified
    notes: str = ""

    def load(self) -> tuple[list[Task], dict[str, Any]]:
        """Eligible tasks (sorted by task id) and a description of their sources."""
        tasks, sources, source_rows, excluded = [], [], 0, Counter()
        for src in self.sources:
            result = _load(src)
            source_rows += result.source_rows
            sources.append({"adapter": src, "adapter_version": result.adapter_version, **dict(result.source)})
            for t in result.tasks:
                if self.include(t):
                    tasks.append(t)
                else:
                    for flag in QUALITY_FLAGS:
                        if flag in t.tags:
                            excluded[QUALITY_FLAGS[flag]] += 1
            excluded.update(f"adapter:{e.reason}" for e in result.exclusions)
        tasks.sort(key=lambda t: t.task_id)
        return tasks, {"sources": sources, "source_rows": source_rows, "eligible": len(tasks),
                       "not_eligible_by_reason": dict(sorted(excluded.items()))}


@lru_cache(maxsize=None)
def _load(src: str) -> AdapterResult:
    kind, _, subset = src.partition(":")
    if kind == "when2call":
        return when2call.load()
    if kind == "metatool":
        return metatool.load(subset)
    if kind == "bfcl":
        return bfcl.load(subset)
    raise KeyError(src)


def _has(flag: str) -> Callable[[Task], bool]:
    return lambda t: flag in t.tags


_W2C_STRATA = {"tool_call": 50, "request_for_info": 50, "cannot_answer": 50}
DATASETS: dict[str, DatasetSpec] = {
    "when2call": DatasetSpec("when2call", "primary", "architecture_matched_v1", ("when2call",),
                             default_sample_size=150, strata=_W2C_STRATA,
                             notes="tool_call / request_for_info / cannot_answer kept distinct; cluster on source_group_id"),
    "metatool_s1": DatasetSpec("metatool_s1", "primary", "ecological_name_description_v1",
                               ("metatool:Task2-Subtask1",), notes="selection-only; gold first in every source row"),
    "metatool_s3": DatasetSpec("metatool_s3", "primary", "ecological_name_description_v1",
                               ("metatool:Task2-Subtask3",), notes="selection-only; correct answer is no tool"),
    "bfcl_simple_python": DatasetSpec("bfcl_simple_python", "primary", "architecture_matched_v1",
                                      ("bfcl:simple_python",), include=_clean),
    "bfcl_multiple": DatasetSpec("bfcl_multiple", "primary", "architecture_matched_v1", ("bfcl:multiple",),
                                 include=_clean),
    "bfcl_live_simple": DatasetSpec("bfcl_live_simple", "primary", "architecture_matched_v1", ("bfcl:live_simple",),
                                    include=_clean),
    "bfcl_live_multiple": DatasetSpec("bfcl_live_multiple", "primary", "architecture_matched_v1",
                                      ("bfcl:live_multiple",), include=_clean),
    "bfcl_irrelevance": DatasetSpec("bfcl_irrelevance", "primary", "architecture_matched_v1", ("bfcl:irrelevance",)),
    "bfcl_live_irrelevance": DatasetSpec("bfcl_live_irrelevance", "primary", "architecture_matched_v1",
                                         ("bfcl:live_irrelevance",)),
    "bfcl_live_relevance": DatasetSpec("bfcl_live_relevance", "sanity_only", "architecture_matched_v1",
                                       ("bfcl:live_relevance",), default_sample_size=5,
                                       notes="5 usable rows; never part of a headline aggregate"),
    **{name: DatasetSpec(name, "diagnostic", "architecture_matched_v1",
                         tuple(f"bfcl:{s}" for s in BFCL_ANSWERED), include=_has(flag), default_sample_size=0,
                         notes=f"items flagged {flag}; excluded from primary BFCL results")
       for flag, name in QUALITY_FLAGS.items()},
}


def task_order_seed(seed: int, task_id: str) -> int:
    """A per-task presentation-order seed, so tasks with equal candidate counts are not all given
    the same permutation."""
    return int(hashlib.sha256(f"order:{seed}:{task_id}".encode()).hexdigest()[:8], 16)


@dataclass(frozen=True)
class DatasetSample:
    spec: DatasetSpec
    tasks: tuple[Task, ...]
    order_seeds: dict[str, int]
    info: dict[str, Any] = field(default_factory=dict)


def sample_dataset(name: str, size: int | None, seed: int, stratify: bool = True) -> DatasetSample:
    spec = DATASETS[name]
    eligible, info = spec.load()
    size = spec.default_sample_size if size is None else size
    if spec.role == "diagnostic" and size == 0:
        size = len(eligible)  # diagnostic subsets are listed whole unless a size is given
    if stratify and spec.strata:
        if size != sum(spec.strata.values()):
            raise SamplingError(f"{name}: stratified size is {sum(spec.strata.values())} ({dict(spec.strata)}), "
                                f"not {size}")
        groups: dict[str, list[Task]] = {}
        for t in eligible:
            groups.setdefault(_label(t), []).append(t)
        chosen = []
        for label, k in spec.strata.items():
            pool = groups.get(label, [])
            if len(pool) < k:
                raise SamplingError(f"{name}: stratum {label!r} has {len(pool)} eligible items, {k} requested")
            chosen += random.Random(f"{seed}:{name}:{label}").sample(pool, k)
    else:
        if len(eligible) < size:
            raise SamplingError(f"{name}: {len(eligible)} eligible items, {size} requested")
        chosen = random.Random(f"{seed}:{name}:all").sample(eligible, size)
    chosen.sort(key=lambda t: t.task_id)
    info = {**info, "sample_size": len(chosen), "stratified": bool(stratify and spec.strata),
            "sampled_by_label": dict(sorted(Counter(_label(t) for t in chosen).items()))}
    return DatasetSample(spec, tuple(chosen), {t.task_id: task_order_seed(seed, t.task_id) for t in chosen}, info)


def diagnostic_items() -> list[dict[str, Any]]:
    """Every BFCL item excluded from primary results for a data-quality flag, with its source id,
    split, original gold (accepted alternatives), original schemas and every applicable reason."""
    from rlcdselect.core.jsonutil import thaw

    out = []
    for subset in BFCL_ANSWERED:
        for t in _load(f"bfcl:{subset}").tasks:
            reasons = [QUALITY_FLAGS[f] for f in QUALITY_FLAGS if f in t.tags]
            if not reasons:
                continue
            p = t.provenance
            gold_key = next(iter(t.expected.tool_keys))
            out.append({
                "task_id": t.task_id, "source_item_id": p["source_item_id"], "source_split": p["source_split"],
                "source_version_or_commit": p["source_version_or_commit"], "exclusion_reasons": reasons,
                "source_gold_function": p["source_gold_function"],
                "original_gold": thaw(t.expected.argument_options),
                "gold_tool_schema": thaw(t.tool(gold_key).input_schema),
                "gold_schema_errors": thaw(p.get("gold_schema_errors")),
                "gold_placeholder_paths": thaw(p.get("gold_placeholder_paths")),
                "gold_empty_alternative_paths": thaw(p.get("gold_empty_alternative_paths")),
            })
    return out
