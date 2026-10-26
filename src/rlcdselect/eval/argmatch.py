"""Matching generated arguments against per-parameter alternatives (BFCL `possible_answer` style).

`options` maps each parameter to the list of accepted values. `""` in the list means the parameter
may be omitted. A nested object alternative is itself an options mapping. This approximates
BFCL's AST checker; it is **not** the official BFCL scorer, and BFCL's overall score is not a
project metric.

- Strings match after BFCL-style standardization: lower-case; spaces and `,./-_*^` removed.
- Numbers: an integer matches an equal float; booleans never match numbers.
- Lists match element by element in order.
- A generated parameter that has no entry in `options` is a mismatch (`unexpected_parameter`).
- An empty list of alternatives (`[]`, which BFCL uses without documenting it) is read as "must be
  omitted or empty": absent, `""`, `[]` and `{}` match; anything else does not. This is an
  interpretation, recorded as such.
"""

import re
from collections.abc import Mapping
from typing import Any

_STRIP = re.compile(r"[ ,./\-_*^]")


def _std(s: str) -> str:
    return _STRIP.sub("", s.lower())


def _scalar_eq(given: Any, accepted: Any) -> bool:
    if isinstance(given, bool) or isinstance(accepted, bool):
        return type(given) is type(accepted) and given == accepted
    if isinstance(given, (int, float)) and isinstance(accepted, (int, float)):
        return float(given) == float(accepted)
    if isinstance(given, str) and isinstance(accepted, str):
        return _std(given) == _std(accepted)
    return given == accepted


def _value_eq(given: Any, accepted: Any) -> bool:
    if isinstance(accepted, Mapping):
        return isinstance(given, Mapping) and not options_mismatches(given, accepted)
    if isinstance(accepted, list):
        return (isinstance(given, list) and len(given) == len(accepted)
                and all(_value_eq(g, a) for g, a in zip(given, accepted)))
    return _scalar_eq(given, accepted)


def options_mismatches(given: Mapping[str, Any], options: Mapping[str, Any], path: str = "") -> list[str]:
    """Empty when `given` satisfies `options`; otherwise one message per failing parameter."""
    problems = []
    for param, accepted in options.items():
        where = f"{path}{param}"
        alts = list(accepted) if isinstance(accepted, list) else [accepted]
        if not alts:  # no accepted value: must be omitted or empty
            if param in given and given[param] not in ("", [], {}):
                problems.append(f"{where}: {given[param]!r} given, but no value is accepted")
            continue
        if param not in given:
            if "" not in alts:
                problems.append(f"{where}: missing")
            continue
        if not any(_value_eq(given[param], a) for a in alts if a != ""):
            problems.append(f"{where}: {given[param]!r} not in accepted values")
    for param in given:
        if param not in options:
            problems.append(f"{path}{param}: unexpected_parameter")
    return problems


def canonical_call(options: Mapping[str, Any]) -> dict[str, Any]:
    """One concrete call that satisfies `options`: the first accepted alternative per parameter,
    recursively for nested options; parameters whose only alternative is `""` are omitted."""
    out = {}
    for param, accepted in options.items():
        alts = list(accepted) if isinstance(accepted, list) else [accepted]
        first = next((a for a in alts if a != ""), _ABSENT)
        if first is _ABSENT:
            continue
        out[param] = _canonical_value(first)
    return out


_ABSENT = object()  # distinct from None: `[None]` accepts a JSON null


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return canonical_call(value)
    if isinstance(value, list):
        return [_canonical_value(v) for v in value]
    return value


def option_leaves(options: Mapping[str, Any], path: str = "") -> list[tuple[str, Any]]:
    """Every concrete scalar accepted anywhere in `options`, with its argument path (list indexes
    as `[*]`), e.g. ('conditions[*].value', '25')."""
    leaves = []
    for param, accepted in options.items():
        where = f"{path}{param}"
        for alt in (accepted if isinstance(accepted, list) else [accepted]):
            leaves += _alt_leaves(alt, where)
    return leaves


def _alt_leaves(alt: Any, where: str) -> list[tuple[str, Any]]:
    if alt == "":
        return []
    if isinstance(alt, Mapping):
        return option_leaves(alt, f"{where}.")
    if isinstance(alt, list):
        out = []
        for el in alt:
            out += option_leaves(el, f"{where}[*].") if isinstance(el, Mapping) else _alt_leaves(el, f"{where}[*]")
        return out
    return [(where, alt)]
