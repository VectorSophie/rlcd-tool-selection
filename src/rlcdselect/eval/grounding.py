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

Severity (grounding policy `refined_v1`, the default since 2026-10-26):

| entry | severity | effect on `argument_grounding_ok` |
|---|---|---|
| explicit, derived, schema_default, fixture_default | `pass` | none |
| placeholder | `hard_failure` | fails |
| unsupported, required argument | `hard_failure` | fails |
| unsupported, argument marked `critical` by the fixture | `hard_failure` | fails |
| unsupported, optional argument | `warning` | none; counted in `unsupported_optional_argument_count` |
| unknown | `neutral` | none; counted |

The previous policy (any unsupported value fails, required or not) is still computed as
`argument_grounding_ok_strict` / `grounded_task_success_strict`, so old analyses stay reproducible.
"Required" means required by the tool schema at every level of the path.

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
- `anaphoric_day`: "that day" / "the same day" resolved to the single explicit date elsewhere in
  the state. With zero or several candidate dates it is not recoverable, so nothing is derived.

Reference date and timezone come from the model-visible state first (`reference_date`,
`current_date`, `today`, `timezone`), then from the task's evaluator-only `evaluation_context`
(`reference_datetime`, `timezone`). Each derived entry records `reference_source` (`state` or
`evaluation_context`), because a date derived from evaluator-only context was not visible to the
model: it shows the value is *consistent with* the task's "now", not that the model could read it.

Evaluator rules (`Task.argument_grounding`), keyed by argument path (`to[0]`, `start.date`; `[*]`
matches any index):

```json
{"to[*]": {"sources": ["state.landlord_email"]},
 "start_date": {"sources": ["state.requested_date"], "allowed_derivations": ["relative_day"]},
 "max_results": {"fixture_default": 10}}
```

`sources` restricts which state paths count as evidence for that argument (dotted, with `[i]`).
`fixture_default` (one value) or `fixture_defaults` (a list) declares permitted defaults.
`critical: true` makes an unsupported value at that path a hard failure even when the argument is
optional (use it for safety- or behavior-critical options). These rules are evaluator-only: they
are never serialized into any selector or LLM input.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.placeholders import DEFAULT_DETECTOR, PlaceholderDetector

STATUSES = ("explicit", "derived", "schema_default", "fixture_default", "placeholder", "unsupported", "unknown")
DERIVATIONS = ("relative_day", "relative_weekday", "date_to_day_start", "date_to_day_end", "token_subset",
               "anaphoric_day")
GROUNDING_POLICY = "refined_v1"
PASS_STATUSES = frozenset({"explicit", "derived", "schema_default", "fixture_default"})
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


def _reference(state: Mapping[str, Any], context: Mapping[str, Any] | None) -> tuple[date | None, str | None]:
    """The reference date and where it came from: model-visible state first, then evaluation context."""
    for key in REFERENCE_DATE_KEYS:
        v = state.get(key) if isinstance(state, Mapping) else None
        if isinstance(v, str):
            try:
                return date.fromisoformat(v[:10]), "state"
            except ValueError:
                return None, None
    v = (context or {}).get("reference_datetime") or (context or {}).get("reference_date")
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10]), "evaluation_context"
        except ValueError:
            return None, None
    return None, None


_THAT_DAY = re.compile(r"\b(?:that|the same) day\b", re.IGNORECASE)


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


def _tz_offset(state: Mapping[str, Any], on: date, context: Mapping[str, Any] | None = None) -> timedelta | None:
    tz = state.get("timezone") if isinstance(state, Mapping) else None
    if not isinstance(tz, str):
        tz = (context or {}).get("timezone")
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
              rules: Mapping[str, Any] | None = None,
              context: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        """Per-path provenance for every scalar leaf of `arguments`, in argument order. `context` is
        the task's evaluator-only `evaluation_context` (reference datetime, timezone)."""
        arguments, schema, state, rules, context = thaw(arguments), thaw(schema), thaw(state), thaw(rules), thaw(context)
        out: dict[str, dict[str, Any]] = {}
        self._walk(arguments, schema, "", True, state, rules, context, out)
        return out

    def _walk(self, value, schema, path, required, state, rules, context, out) -> None:
        if isinstance(value, Mapping):
            req = set((schema or {}).get("required") or ()) if isinstance(schema, Mapping) else set()
            for k, v in value.items():
                child = f"{path}.{k}" if path else str(k)
                self._walk(v, _child_schema(schema, k), child, (k in req) and required, state, rules, context, out)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                self._walk(v, _child_schema(schema, i), f"{path}[{i}]", required, state, rules, context, out)
        else:
            rule = _rule_for(path, rules)
            entry = self._leaf(value, schema, path, state, rule, context)
            entry["required"] = required
            entry["critical"] = bool(rule.get("critical"))
            entry["severity"] = severity(entry)
            out[path or "<root>"] = entry

    def _leaf(self, value, schema, path, state, rule, context=None) -> dict[str, Any]:
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
        ref, ref_source = _reference(state, context)
        all_texts = [(p, v) for p, v in state_leaves(state) if isinstance(v, str)]

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
            found = self._ground_date(target, texts, ref, derivations, all_texts)
            if not found:
                return result("unsupported")
            entry = result(*found)
            if found[0] == "derived" and found[2] in ("relative_day", "relative_weekday"):
                entry["reference_source"] = ref_source
            return entry

        if vtype == "datetime":
            entry = self._ground_datetime(value, texts, ref, derivations, state, result, all_texts, context)
            if entry["status"] == "derived" and entry["how"] and entry["how"].startswith("relative_"):
                entry["reference_source"] = ref_source
            return entry

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
    def _ground_date(target: date, texts, ref: date | None, derivations, all_texts=()) -> tuple[str, str, str | None] | None:
        for p, v in texts:
            if target in _dates_in(v):
                return "explicit", p, None
        if ref is not None:
            for p, v in texts:
                for d, how in _relative_dates(v, ref):
                    if d == target and how in derivations:
                        return "derived", p, how
        if "anaphoric_day" in derivations:
            candidates = {d for _, v in all_texts for d in _dates_in(v)}
            if len(candidates) == 1 and target in candidates:  # exactly one antecedent date
                for p, v in texts:
                    if _THAT_DAY.search(v):
                        return "derived", p, "anaphoric_day"
        return None

    def _ground_datetime(self, value: str, texts, ref, derivations, state, result, all_texts=(),
                         context=None) -> dict[str, Any]:
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
        grounded = self._ground_date(dt.date(), texts, ref, derivations, all_texts)
        if grounded is None:
            return result("unsupported")
        _, source, how = grounded
        boundary = ("date_to_day_start" if dt.time().replace(tzinfo=None) == time(0)
                    else "date_to_day_end" if (dt.hour, dt.minute, dt.second) == (23, 59, 59) else None)
        if boundary is None or boundary not in derivations:
            return result("unknown", source, "time_of_day_not_traced")
        if dt.utcoffset() is not None:
            expected = _tz_offset(state, dt.date(), context)
            if expected is None:
                return result("unknown", source, "timezone_not_traced")
            if dt.utcoffset() != expected:
                return result("unsupported", source, "timezone_mismatch")
        return result("derived", source, boundary if how is None else f"{how}+{boundary}")


DEFAULT_CHECKER = GroundingChecker()


def severity(entry: Mapping[str, Any]) -> str:
    """`pass`, `hard_failure`, `warning` or `neutral` for one provenance entry (policy `refined_v1`).
    Works on entries written before severities were recorded."""
    status = entry.get("status")
    if status in PASS_STATUSES:
        return "pass"
    if status == "placeholder":
        return "hard_failure"
    if status == "unsupported":
        return "hard_failure" if entry.get("required") or entry.get("critical") else "warning"
    return "neutral"


def ground_arguments(arguments: Mapping[str, Any] | None, schema: Mapping[str, Any] | None,
                     state: Mapping[str, Any], rules: Mapping[str, Any] | None = None,
                     checker: GroundingChecker = DEFAULT_CHECKER,
                     context: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]] | None:
    return None if arguments is None else checker.check(arguments, schema, state, rules, context)


def grounding_summary(provenance: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    """Counts and both overall flags. `argument_grounding_ok` (refined_v1) is False only on a hard
    failure: a placeholder, or an unsupported required or critical value. `argument_grounding_ok_strict`
    is the previous policy: False on any placeholder or unsupported value. None when no arguments
    were generated."""
    keys = ("argument_grounding_ok", "argument_grounding_ok_strict", "placeholder_argument_count",
            "unsupported_argument_count", "unsupported_required_argument_count",
            "unsupported_optional_argument_count", "unknown_argument_count", "grounding_warning_count")
    if provenance is None:
        return {"grounding_policy": GROUNDING_POLICY, **{k: None for k in keys}}
    entries = list(provenance.values())
    statuses = [e["status"] for e in entries]
    severities = [e.get("severity") or severity(e) for e in entries]
    unsupported = [e for e in entries if e["status"] == "unsupported"]
    return {
        "grounding_policy": GROUNDING_POLICY,
        "argument_grounding_ok": "hard_failure" not in severities,
        "argument_grounding_ok_strict": "placeholder" not in statuses and "unsupported" not in statuses,
        "placeholder_argument_count": statuses.count("placeholder"),
        "unsupported_argument_count": len(unsupported),
        "unsupported_required_argument_count": sum(1 for e in unsupported if e.get("required")),
        "unsupported_optional_argument_count": sum(1 for e in unsupported if not e.get("required")),
        "unknown_argument_count": statuses.count("unknown"),
        "grounding_warning_count": severities.count("warning"),
    }


def grounded_task_success(task_success: bool, abstention_expected: bool, grounding_ok: bool | None) -> bool:
    """Stricter task success: an action task also needs grounded arguments. Abstention tasks are
    unchanged (nothing should have been generated). Pass `argument_grounding_ok` for the refined
    metric or `argument_grounding_ok_strict` for the strict one."""
    if abstention_expected:
        return task_success
    return bool(task_success) and grounding_ok is True


def ground_record(record: Mapping[str, Any], rules: Mapping[str, Any] | None = None,
                  context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Grounding fields for an existing record, without modifying it (used to rescore old runs).
    `rules` / `context` override the record's own `expected.argument_grounding` /
    `expected.evaluation_context` (absent in older records)."""
    tool = next((t for t in record.get("tools_before") or () if t.get("key") == record.get("selected_tool")), None)
    expected = record.get("expected") or {}
    rules = rules if rules is not None else expected.get("argument_grounding")
    context = context if context is not None else expected.get("evaluation_context")
    provenance = ground_arguments(record.get("arguments"), tool.get("input_schema") if tool else None,
                                  record.get("state") or {}, rules, context=context)
    summary = grounding_summary(provenance)
    ts, abst = record.get("task_success"), record.get("abstention_expected")
    return {"argument_provenance": provenance, **summary,
            "grounded_task_success": grounded_task_success(ts, abst, summary["argument_grounding_ok"]),
            "grounded_task_success_strict": grounded_task_success(ts, abst, summary["argument_grounding_ok_strict"])}


def status_counts(provenance: Iterable[Mapping[str, Mapping[str, Any]] | None]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for p in provenance:
        for e in (p or {}).values():
            counts[e["status"]] += 1
    return counts


__all__: Sequence[str] = ("GroundingChecker", "ground_arguments", "grounding_summary", "grounded_task_success",
                          "ground_record", "status_counts", "STATUSES", "DERIVATIONS")
