"""Deterministic argument provenance (grounding).

For every scalar leaf of a generated argument object, decide where its value came from. No model
is involved: an LLM judge would add a second model's decisions to the measurement.

Statuses, checked in this order:

| status | meaning |
|---|---|
| `placeholder` | the whole string is a placeholder (`core.placeholders`), e.g. `<UNKNOWN>`, `TBD`, `???` |
| `fixture_default` | equals a default the task fixture permits for this path (evaluator-only metadata) |
| `schema_default` | equals the tool schema's own `default` (or `const`) for this path |
| `explicit` | appears in the task state, directly or as a normalized equivalent (case, whitespace and surrounding punctuation; date formats; number words up to twenty) |
| `derived` | follows from explicit state by one of the implemented derivations below |
| `unsupported` | a *typed* concrete value (email, date, date-time, number, URL) that none of the above explains |
| `unknown` | the checker cannot decide: free text the model composed, booleans, nulls, a time of day it cannot trace |

`unsupported` is only used for typed values, where absence from the state is meaningful.
Free text that is not found is `unknown`, never `unsupported`: a composed email body is not a
fabrication just because its words are new.

Derivations (each one explicit and reproducible; a fixture can restrict them per path):

- `relative_day`: "today" / "tomorrow" / "yesterday" / "the day after tomorrow" resolved against a
  reference date in the state (`reference_date`, `current_date` or `today`, ISO format).
- `relative_weekday`: a weekday name ("Monday", "this Monday", "next Monday") resolved against the
  reference date. "Next" is ambiguous in English, so both the first occurrence after the
  reference date and the one a week later are accepted.
- `date_to_day_start` / `date_to_day_end`: a date-time at 00:00:00 or 23:59:59 of an explicit or
  derived date. A UTC offset on the value must match the state's `timezone` (an IANA name or
  `±HH:MM`) on that date; an offset with no timezone in the state is `unknown`.
- `token_subset`: every alphanumeric token of a text value appears in one state string (e.g. a
  reordered search query). Recorded as `derived`, not `explicit`, because the wording changed.

Evaluator rules (`Task.argument_grounding`), keyed by argument path (`to[0]`, `start.date`; `[*]`
matches any index):

```json
{"to[*]": {"sources": ["state.landlord_email"]},
 "start_date": {"sources": ["state.requested_date"], "allowed_derivations": ["relative_day"]},
 "max_results": {"fixture_default": 10}}
```

`sources` restricts which state paths count as evidence for that argument (dotted, with `[i]`).
`fixture_default` (one value) or `fixture_defaults` (a list) declares permitted defaults. These
rules are evaluator-only: they are never serialized into any selector or LLM input.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.placeholders import DEFAULT_DETECTOR, PlaceholderDetector

STATUSES = ("explicit", "derived", "schema_default", "fixture_default", "placeholder", "unsupported", "unknown")
DERIVATIONS = ("relative_day", "relative_weekday", "date_to_day_start", "date_to_day_end", "token_subset")
REFERENCE_DATE_KEYS = ("reference_date", "current_date", "today")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?!\w)")
_TOKEN = re.compile(r"[a-z0-9]+")
_MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_MDY = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.IGNORECASE)
_DATE_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\.?,?\s+(\d{{4}})\b", re.IGNORECASE)
_NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_WEEKDAYS = {w: i for i, w in enumerate("monday tuesday wednesday thursday friday saturday sunday".split())}
_RELATIVE_DAYS = (("the day after tomorrow", 2), ("tomorrow", 1), ("today", 0), ("tonight", 0), ("yesterday", -1))
_EDGE_PUNCT = " \t\r\n.,;:!?\"'`()[]{}"


# --- state evidence ----------------------------------------------------------------------------

def state_leaves(value: Any, path: str = "state") -> list[tuple[str, Any]]:
    """Every scalar in the state with its dotted path, e.g. ('state.contacts[0].email', '...')."""
    if isinstance(value, Mapping):
        return [leaf for k, v in value.items() for leaf in state_leaves(v, f"{path}.{k}")]
    if isinstance(value, (list, tuple)):
        return [leaf for i, v in enumerate(value) for leaf in state_leaves(v, f"{path}[{i}]")]
    return [(path, value)]


def _norm_text(s: str) -> str:
    return " ".join(s.casefold().split()).strip(_EDGE_PUNCT)


def _dates_in(text: str) -> list[date]:
    found = []
    for m in _ISO_DATE.finditer(text):
        try:
            found.append(date.fromisoformat(m.group()))
        except ValueError:
            pass
    for m in _DATE_MDY.finditer(text):
        found += _safe_date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    for m in _DATE_DMY.finditer(text):
        found += _safe_date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    return found


def _safe_date(y: int, m: int, d: int) -> list[date]:
    try:
        return [date(y, m, d)]
    except ValueError:
        return []


def _reference_date(state: Mapping[str, Any]) -> date | None:
    for key in REFERENCE_DATE_KEYS:
        v = state.get(key) if isinstance(state, Mapping) else None
        if isinstance(v, str):
            try:
                return date.fromisoformat(v[:10])
            except ValueError:
                return None
    return None


def _relative_dates(text: str, ref: date) -> list[tuple[date, str]]:
    t = text.casefold()
    out = []
    for phrase, offset in _RELATIVE_DAYS:
        if re.search(rf"\b{phrase}\b", t):
            out.append((ref + timedelta(days=offset), "relative_day"))
    for m in re.finditer(r"\b(?:(next|this|on|coming)\s+)?(" + "|".join(_WEEKDAYS) + r")\b", t):
        target = _WEEKDAYS[m.group(2)]
        ahead = (target - ref.weekday()) % 7
        candidates = {ref + timedelta(days=ahead)}  # on or after the reference date
        if ahead == 0 or m.group(1) == "next":
            candidates.add(ref + timedelta(days=ahead or 7))
        if m.group(1) == "next":
            candidates.add(ref + timedelta(days=(ahead or 7) + 7))  # "next" = the week after
        out += [(d, "relative_weekday") for d in sorted(candidates)]
    return out


def _tz_offset(state: Mapping[str, Any], on: date) -> timedelta | None:
    tz = state.get("timezone") if isinstance(state, Mapping) else None
    if not isinstance(tz, str):
        return None
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", tz.strip())
    if m:
        sign = 1 if m.group(1) == "+" else -1
        return sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    if tz.strip().upper() in ("UTC", "Z", "GMT"):
        return timedelta(0)
    try:
        return datetime.combine(on, time(12), ZoneInfo(tz.strip())).utcoffset()
    except (ZoneInfoNotFoundError, ValueError):
        return None


# --- schema helpers --------------------------------------------------------------------------

def _child_schema(schema: Mapping[str, Any] | None, key: str | int) -> Mapping[str, Any] | None:
    if not isinstance(schema, Mapping):
        return None
    if isinstance(key, int):
        items = schema.get("items")
        return items if isinstance(items, Mapping) else None
    props = schema.get("properties")
    return props.get(key) if isinstance(props, Mapping) else None


def _value_type(value: Any, schema: Mapping[str, Any] | None) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "null"
    if not isinstance(value, str):
        return "other"
    fmt = (schema or {}).get("format")
    if fmt == "email" or _EMAIL.fullmatch(value.strip()):
        return "email"
    if fmt == "date" or _ISO_DATE.fullmatch(value.strip()):
        return "date"
    if fmt == "date-time" or _ISO_DATETIME.fullmatch(value.strip()):
        return "datetime"
    if fmt in ("uri", "url") or _URL.fullmatch(value.strip()):
        return "url"
    return "text"


# --- rules -----------------------------------------------------------------------------------

def _rule_for(path: str, rules: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not rules:
        return {}
    if path in rules:
        return rules[path]
    for pattern, rule in rules.items():
        regex = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]")
        if re.fullmatch(regex, path):
            return rule
    return {}


# --- the checker -----------------------------------------------------------------------------

class GroundingChecker:
    def __init__(self, detector: PlaceholderDetector = DEFAULT_DETECTOR) -> None:
        self.detector = detector

    def check(self, arguments: Mapping[str, Any], schema: Mapping[str, Any] | None, state: Mapping[str, Any],
              rules: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        """Per-path provenance for every scalar leaf of `arguments`, in argument order."""
        arguments, schema, state, rules = thaw(arguments), thaw(schema), thaw(state), thaw(rules)
        out: dict[str, dict[str, Any]] = {}
        self._walk(arguments, schema, "", True, state, rules, out)
        return out

    def _walk(self, value, schema, path, required, state, rules, out) -> None:
        if isinstance(value, Mapping):
            req = set((schema or {}).get("required") or ()) if isinstance(schema, Mapping) else set()
            for k, v in value.items():
                child = f"{path}.{k}" if path else str(k)
                self._walk(v, _child_schema(schema, k), child, (k in req) and required, state, rules, out)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                self._walk(v, _child_schema(schema, i), f"{path}[{i}]", required, state, rules, out)
        else:
            entry = self._leaf(value, schema, path, state, _rule_for(path, rules))
            entry["required"] = required
            out[path or "<root>"] = entry

    def _leaf(self, value, schema, path, state, rule) -> dict[str, Any]:
        vtype = _value_type(value, schema)

        def result(status, source=None, how=None):
            return {"status": status, "source": source, "how": how, "value_type": vtype}

        if self.detector.is_placeholder(value):
            return result("placeholder")
        defaults = list(rule.get("fixture_defaults") or ()) + (
            [rule["fixture_default"]] if "fixture_default" in rule else [])
        if any(value == d and type(value) is type(d) for d in defaults):
            return result("fixture_default", "fixture.argument_grounding")
        if isinstance(schema, Mapping):
            for key in ("default", "const"):
                if key in schema and schema[key] == value and type(schema[key]) is type(value):
                    return result("schema_default", f"schema.{key}")

        leaves = state_leaves(state)
        if rule.get("sources"):
            allowed = tuple(rule["sources"])
            leaves = [(p, v) for p, v in leaves if any(p == a or p.startswith((a + ".", a + "[")) for a in allowed)]
        derivations = tuple(rule.get("allowed_derivations", DERIVATIONS))
        texts = [(p, v) for p, v in leaves if isinstance(v, str)]
        ref = _reference_date(state)

        if vtype == "email":
            for p, v in texts:
                if value.strip().lower() in {e.lower() for e in _EMAIL.findall(v)}:
                    return result("explicit", p)
            return result("unsupported")

        if vtype == "date":
            try:
                target = date.fromisoformat(value.strip())
            except ValueError:
                return result("unknown")
            found = self._ground_date(target, texts, ref, derivations)
            return result(*found) if found else result("unsupported")

        if vtype == "datetime":
            return self._ground_datetime(value, texts, ref, derivations, state, result)

        if vtype == "number":
            for p, v in leaves:
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v == value:
                    return result("explicit", p)
            for p, v in texts:
                if any(float(n) == value for n in _NUMBER.findall(v)):
                    return result("explicit", p)
                words = set(_TOKEN.findall(v.casefold()))
                if any(_NUMBER_WORDS.get(w) == value for w in words):
                    return result("explicit", p, "number_word")
            return result("unsupported")

        if vtype == "url":
            want = value.strip().rstrip("/").lower()
            for p, v in texts:
                if any(u.rstrip("/.,").lower() == want for u in _URL.findall(v)):
                    return result("explicit", p)
            return result("unsupported")

        if vtype == "text":
            want = _norm_text(value)
            if want:
                for p, v in texts:
                    if want in _norm_text(v):
                        return result("explicit", p)
                if "token_subset" in derivations:
                    tokens = set(_TOKEN.findall(want))
                    for p, v in texts:
                        if tokens and tokens <= set(_TOKEN.findall(v.casefold())):
                            return result("derived", p, "token_subset")
            return result("unknown")

        return result("unknown")  # booleans, nulls, anything else

    @staticmethod
    def _ground_date(target: date, texts, ref: date | None, derivations) -> tuple[str, str, str | None] | None:
        for p, v in texts:
            if target in _dates_in(v):
                return "explicit", p, None
        if ref is not None:
            for p, v in texts:
                for d, how in _relative_dates(v, ref):
                    if d == target and how in derivations:
                        return "derived", p, how
        return None

    def _ground_datetime(self, value: str, texts, ref, derivations, state, result) -> dict[str, Any]:
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return result("unknown")
        for p, v in texts:
            for m in _ISO_DATETIME.finditer(v):
                try:
                    if datetime.fromisoformat(m.group().replace("Z", "+00:00")) == dt:
                        return result("explicit", p)
                except ValueError:
                    pass
        grounded = self._ground_date(dt.date(), texts, ref, derivations)
        if grounded is None:
            return result("unsupported")
        _, source, how = grounded
        boundary = ("date_to_day_start" if dt.time().replace(tzinfo=None) == time(0)
                    else "date_to_day_end" if (dt.hour, dt.minute, dt.second) == (23, 59, 59) else None)
        if boundary is None or boundary not in derivations:
            return result("unknown", source, "time_of_day_not_traced")
        if dt.utcoffset() is not None:
            expected = _tz_offset(state, dt.date())
            if expected is None:
                return result("unknown", source, "timezone_not_traced")
            if dt.utcoffset() != expected:
                return result("unsupported", source, "timezone_mismatch")
        return result("derived", source, boundary if how is None else f"{how}+{boundary}")


DEFAULT_CHECKER = GroundingChecker()


def ground_arguments(arguments: Mapping[str, Any] | None, schema: Mapping[str, Any] | None,
                     state: Mapping[str, Any], rules: Mapping[str, Any] | None = None,
                     checker: GroundingChecker = DEFAULT_CHECKER) -> dict[str, dict[str, Any]] | None:
    return None if arguments is None else checker.check(arguments, schema, state, rules)


def grounding_summary(provenance: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    """Counts and the overall flag. `argument_grounding_ok` is False when any value is a placeholder
    or unsupported; `unknown` values do not fail it. None when no arguments were generated."""
    if provenance is None:
        return {"argument_grounding_ok": None, "placeholder_argument_count": None,
                "unsupported_argument_count": None, "unknown_argument_count": None,
                "unsupported_required_argument_count": None}
    statuses = [e["status"] for e in provenance.values()]
    return {
        "argument_grounding_ok": "placeholder" not in statuses and "unsupported" not in statuses,
        "placeholder_argument_count": statuses.count("placeholder"),
        "unsupported_argument_count": statuses.count("unsupported"),
        "unknown_argument_count": statuses.count("unknown"),
        "unsupported_required_argument_count": sum(
            1 for e in provenance.values() if e["status"] == "unsupported" and e.get("required")),
    }


def grounded_task_success(task_success: bool, abstention_expected: bool, grounding_ok: bool | None) -> bool:
    """Stricter task success: an action task also needs grounded arguments. Abstention tasks are
    unchanged (nothing should have been generated)."""
    if abstention_expected:
        return task_success
    return bool(task_success) and grounding_ok is True


def ground_record(record: Mapping[str, Any], rules: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Grounding fields for an existing record, without modifying it (used to rescore old runs).
    `rules` overrides the record's own `expected.argument_grounding` (absent in pre-v3 records)."""
    tool = next((t for t in record.get("tools_before") or () if t.get("key") == record.get("selected_tool")), None)
    rules = rules if rules is not None else (record.get("expected") or {}).get("argument_grounding")
    provenance = ground_arguments(record.get("arguments"), tool.get("input_schema") if tool else None,
                                  record.get("state") or {}, rules)
    summary = grounding_summary(provenance)
    return {"argument_provenance": provenance, **summary,
            "grounded_task_success": grounded_task_success(record.get("task_success"),
                                                           record.get("abstention_expected"),
                                                           summary["argument_grounding_ok"])}


def status_counts(provenance: Iterable[Mapping[str, Mapping[str, Any]] | None]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for p in provenance:
        for e in (p or {}).values():
            counts[e["status"]] += 1
    return counts


__all__: Sequence[str] = ("GroundingChecker", "ground_arguments", "grounding_summary", "grounded_task_success",
                          "ground_record", "status_counts", "STATUSES", "DERIVATIONS")
