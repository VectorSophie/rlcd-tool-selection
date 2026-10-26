"""Metrics over run records.

Primary, cross-architecture metrics use only discrete outcomes (`selection_label`). Reported
probabilities are used only for clean→perturbed shift *within one selector* and one probability
kind; `probability_shift` refuses any other comparison.
"""

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from rlcdselect.core.types import ABSTAIN
from rlcdselect.eval.stability import samples_of, selector_stability, summarize_samples  # noqa: F401 (re-export)

FAILED = "__failed__"  # discrete label for selector errors / multiple calls in frequency tables


class IncomparableProbabilitiesError(ValueError):
    """Raised when asked to compare probabilities across selectors, kinds, or invalid outputs."""


def _rate(values: Iterable[bool | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _median(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def _sum_usage(records: Sequence[Mapping[str, Any]], field: str, key: str) -> int | None:
    vals = [(r.get(field) or {}).get(key) for r in records]
    known = [v for v in vals if v is not None]
    return sum(known) if known else None


def summarize(records: Sequence[Mapping[str, Any]], group_by: str = "pipeline") -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in records:
        if r.get("record_type", "run") != "run":
            continue
        groups[r[group_by]].append(r)
    out = {}
    for name, rs in sorted(groups.items()):
        act = [r for r in rs if not r["abstention_expected"]]
        abst = [r for r in rs if r["abstention_expected"]]
        roles = Counter(r["selected_role"] or FAILED for r in rs)
        out[name] = {
            "n": len(rs),
            "selection_accuracy": _rate(r["selection_correct"] for r in act),
            "abstention_accuracy": _rate(r["selection_correct"] for r in abst),
            "false_abstention_rate": _rate(r["selection_label"] == ABSTAIN for r in act),
            "false_action_rate": _rate(r["selection_label"] not in (ABSTAIN, None) for r in abst),
            "selector_error_rate": _rate(r["selector_error"] for r in rs),
            "argument_error_rate": _rate(r["argument_error"] for r in rs if r["selection_status"] == "selected"),
            "argument_schema_valid_rate": _rate(r["arguments_schema_valid"] for r in rs),
            "argument_match_rate": _rate(r["arguments_match"] for r in rs),
            "execution_success_rate": _rate(r["execution_success"] for r in rs),
            "task_success_rate": _rate(r["task_success"] for r in rs),
            "role_selection_rates": {k: v / len(rs) for k, v in sorted(roles.items())},
            "median_selection_latency_ms": _median(r["selection_latency_ms"] for r in rs),
            "median_total_latency_ms": _median(r["total_latency_ms"] for r in rs),
            "selector_input_tokens": _sum_usage(rs, "selector_usage", "input_tokens"),
            "selector_output_tokens": _sum_usage(rs, "selector_usage", "output_tokens"),
            "argument_input_tokens": _sum_usage(rs, "argument_usage", "input_tokens"),
            "argument_output_tokens": _sum_usage(rs, "argument_usage", "output_tokens"),
            "total_retries": sum(r["retry_count"] for r in rs),
        }
    return out


def selection_frequencies(
    records: Sequence[Mapping[str, Any]],
    key: Callable[[Mapping[str, Any]], Any] = lambda r: (r["pipeline"], r["task_id"]),
) -> dict[Any, dict[str, float]]:
    """Empirical distribution of discrete outcomes per group (the primary cross-arm distribution)."""
    groups: dict[Any, Counter] = defaultdict(Counter)
    for r in records:
        if r.get("record_type", "run") != "run":
            continue
        groups[key(r)][r["selection_label"] or FAILED] += 1
    return {g: {label: c / sum(cnt.values()) for label, c in sorted(cnt.items())} for g, cnt in groups.items()}


def _support(p: Mapping[str, float], q: Mapping[str, float]) -> list[str]:
    return sorted(set(p) | set(q))


def total_variation(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in _support(p, q))


def entropy(p: Mapping[str, float]) -> float:
    """Shannon entropy in bits."""
    return -sum(v * math.log2(v) for v in p.values() if v > 0)


def js_divergence(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    """Jensen–Shannon divergence in bits (0..1)."""
    keys = _support(p, q)
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a: Mapping[str, float]) -> float:
        return sum(a.get(k, 0.0) * math.log2(a.get(k, 0.0) / m[k]) for k in keys if a.get(k, 0.0) > 0)

    return 0.5 * kl(p) + 0.5 * kl(q)


def distribution_shift(clean: Mapping[str, float], perturbed: Mapping[str, float]) -> dict[str, Any]:
    keys = _support(clean, perturbed)
    return {
        "delta": {k: perturbed.get(k, 0.0) - clean.get(k, 0.0) for k in keys},
        "total_variation": total_variation(clean, perturbed),
        "js_divergence": js_divergence(clean, perturbed),
        "entropy_change": entropy(perturbed) - entropy(clean),
    }


def probability_shift(clean: Mapping[str, Any], perturbed: Mapping[str, Any]) -> dict[str, Any]:
    """Within-selector shift of reported probabilities between a clean and a perturbed run.

    Probabilities are aligned by stable tool key. Refuses records from different selectors,
    different probability kinds, missing probabilities, or probabilities flagged as invalid.
    """
    for field in ("pipeline", "selector_id", "selector_model", "probability_kind"):
        if clean.get(field) != perturbed.get(field):
            raise IncomparableProbabilitiesError(
                f"{field} differs ({clean.get(field)!r} vs {perturbed.get(field)!r}); "
                "probabilities are only comparable within one selector")
    if clean["probability_kind"] == "none":
        raise IncomparableProbabilitiesError("Selector reports no probabilities")
    for name, r in (("clean", clean), ("perturbed", perturbed)):
        if r.get("selection_probabilities_by_tool") is None:
            raise IncomparableProbabilitiesError(f"{name} record has no probabilities")
        if r.get("probability_issues"):
            raise IncomparableProbabilitiesError(f"{name} record has invalid probabilities: {r['probability_issues']}")
    result = distribution_shift(clean["selection_probabilities_by_tool"], perturbed["selection_probabilities_by_tool"])
    result["probability_kind"] = clean["probability_kind"]
    return result
