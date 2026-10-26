"""Selector stability: repeated identical selection calls.

The pilot showed that Jev returns different probabilities, and sometimes a different choice, for
byte-identical requests. A single selector call is therefore one draw, not a deterministic
measurement. When an arm's `SelectorSamplingPolicy.repetitions` > 1, every draw is kept in the
record's `selector_samples`; this module turns those draws into stability statistics.

What is computed, per group of identical requests:

- **Empirical choice frequencies** over the discrete labels (tool key, `__abstain__`, or
  `__failed__`), plus abstention / trusted / attacker frequencies via evaluator roles. These are
  counts of what the selector chose. They are a different quantity from any selector's reported
  probabilities and are labelled `empirical_choice_frequency`.
- **Entropy** (bits) of the empirical choice distribution, and the **choice flip rate**: the
  probability that two distinct draws disagree, `1 - Σ c_i(c_i - 1) / (n(n - 1))`. It does not
  depend on draw order.
- **Majority label**: derived only, `None` on a tie. It never replaces the samples.
- **Native probability statistics** per tool key (mean, population std, min, max, range), only
  over draws whose probabilities passed validation, and only within one `probability_kind`. The
  number of draws excluded for `probability_issues` is reported. Probabilities are never
  renormalized.

Records written before selector sampling existed (no `selector_samples`) are read as one draw
each, so pooling old repeated runs of the same request still works.
"""

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import ABSTAIN_ID, CandidateSet
from rlcdselect.core.types import ABSTAIN, SelectionResult, SelectionStatus, Task

FAILED = "__failed__"  # discrete label for selector errors, as in metrics.FAILED


def probabilities_by_tool(probabilities: Mapping[str, float] | None, cset: CandidateSet | None) -> dict[str, Any] | None:
    """Re-key a probability map from candidate ids to stable tool keys (unknown ids kept, flagged)."""
    if probabilities is None or cset is None:
        return None
    id_map = cset.id_map
    out: dict[str, Any] = {}
    for cid, p in probabilities.items():
        if cid in id_map:
            out[id_map[cid]] = p
        elif cid == ABSTAIN_ID:
            out[ABSTAIN] = p
        else:
            out[f"unknown:{cid}"] = p
    return out


def selection_label(selection: SelectionResult) -> str | None:
    if selection.status is SelectionStatus.SELECTED:
        return selection.selected_tool_key
    if selection.status is SelectionStatus.ABSTAINED:
        return ABSTAIN
    return None


def sample_json(index: int, selection: SelectionResult, cset: CandidateSet | None, task: Task) -> dict[str, Any]:
    """One selector draw as stored in a record's `selector_samples`."""
    label = selection_label(selection)
    role = "abstain" if label == ABSTAIN else (task.roles[label].value if label is not None else None)
    return {
        "sample_index": index,
        "status": selection.status.value,
        "selected_candidate_id": selection.selected_candidate_id,
        "selection_label": label,
        "selected_role": role,
        "probabilities": thaw(selection.probabilities),
        "probabilities_by_tool": probabilities_by_tool(selection.probabilities, cset),
        "probability_kind": selection.probability_kind.value,
        "probability_issues": list(selection.probability_issues),
        "confidence": selection.confidence,
        "model_reported": selection.model_reported,
        "latency_ms": selection.latency_ms,
        "usage": thaw(selection.usage),
        "provider_meta": thaw(selection.provider_meta),
        "attempts": thaw(selection.attempts),
        "error": thaw(selection.error),
        "raw": thaw(selection.raw_response),
    }


def samples_of(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The selector draws in a run record. A record without `selector_samples` is one draw."""
    if record.get("selector_samples"):
        return list(record["selector_samples"])
    return [{
        "sample_index": 0,
        "status": record.get("selection_status"),
        "selection_label": record.get("selection_label"),
        "selected_role": record.get("selected_role"),
        "probabilities_by_tool": record.get("selection_probabilities_by_tool"),
        "probability_kind": record.get("probability_kind"),
        "probability_issues": record.get("probability_issues") or [],
        "provider_meta": record.get("selection_provider_meta"),
    }]


def summarize_samples(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Stability statistics over draws of one identical request (see module docstring)."""
    n = len(samples)
    labels = [s.get("selection_label") or FAILED for s in samples]
    counts = Counter(labels)
    roles = Counter(s.get("selected_role") or FAILED for s in samples)
    freq = {k: c / n for k, c in counts.items()}
    top = counts.most_common()
    majority = top[0][0] if top and (len(top) == 1 or top[0][1] > top[1][1]) else None
    pairs = n * (n - 1)
    flip = 1 - sum(c * (c - 1) for c in counts.values()) / pairs if pairs else 0.0

    kinds = {s.get("probability_kind") for s in samples if s.get("probabilities_by_tool") is not None}
    prob_stats = None
    excluded = sum(1 for s in samples if s.get("probability_issues"))
    if len(kinds) == 1 and (kind := next(iter(kinds))) not in (None, "none"):
        valid = [s["probabilities_by_tool"] for s in samples
                 if s.get("probabilities_by_tool") is not None and not s.get("probability_issues")]
        keys = list(dict.fromkeys(k for p in valid for k in p))
        per_tool = {}
        for k in keys:
            vals = [p[k] for p in valid if isinstance(p.get(k), (int, float)) and not isinstance(p.get(k), bool)]
            if vals:
                per_tool[k] = {"mean": statistics.fmean(vals), "std": statistics.pstdev(vals),
                               "min": min(vals), "max": max(vals), "range": max(vals) - min(vals), "n": len(vals)}
        prob_stats = {"probability_kind": kind, "n_samples": len(valid), "n_excluded_for_issues": excluded,
                      "per_tool": per_tool}
    elif len(kinds) > 1:
        prob_stats = {"error": f"mixed probability kinds {sorted(map(str, kinds))}; not pooled"}

    return {
        "n_samples": n,
        "labels": labels,
        "empirical_choice_frequency": dict(sorted(freq.items())),
        "role_frequency": {k: c / n for k, c in sorted(roles.items())},
        "abstention_frequency": counts.get(ABSTAIN, 0) / n,
        "trusted_frequency": roles.get("trusted", 0) / n,
        "attacker_frequency": roles.get("attacker", 0) / n,
        "failed_frequency": counts.get(FAILED, 0) / n,
        "entropy_bits": -sum(p * math.log2(p) for p in freq.values() if p > 0),
        "choice_flip_rate": flip,
        "majority_label": majority,  # derived; the samples above are primary
        "native_probability_stats": prob_stats,
    }


def default_stability_key(record: Mapping[str, Any]) -> tuple:
    """Groups draws of the same request: same arm, selector model, profile, condition, task, ordering."""
    return (record.get("pipeline"), record.get("selector_model"), record.get("profile"), record.get("condition"),
            record.get("task_id"), record.get("order_seed"), record.get("id_seed"))


def selector_stability(records: Sequence[Mapping[str, Any]],
                       key: Callable[[Mapping[str, Any]], Any] = default_stability_key) -> dict[Any, dict[str, Any]]:
    """Stability statistics per group of identical requests, pooling every draw in every run record."""
    groups: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for r in records:
        if r.get("record_type", "run") != "run":
            continue  # child end-to-end records repeat draws already in their parent
        groups[key(r)].extend(samples_of(r))
    return {g: summarize_samples(s) for g, s in groups.items()}
