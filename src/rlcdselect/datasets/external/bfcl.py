"""BFCL v4 (Berkeley Function Calling Leaderboard, Apache-2.0) → project tasks, for the subsets that
fit a single-choice, single-call, stateless harness. BFCL's overall score is not a project metric.

Included subsets (`common.BFCL_INCLUDED_SUBSETS`) and their outcome:

| subset | outcome | gold arguments |
|---|---|---|
| `simple_python`, `live_simple` | the one listed function | `possible_answer` alternatives |
| `multiple`, `live_multiple` | the ground-truth function among several | `possible_answer` alternatives |
| `irrelevance`, `live_irrelevance` | abstain (`no_suitable_tool`) | none |
| `live_relevance` | the function, only when exactly one is listed (BFCL gives no gold function) | none |

Excluded subsets and why: `common.BFCL_EXCLUDED_SUBSETS` (parallel, multi-turn, memory, web search,
Java/JavaScript-typed schemas, format sensitivity).

Row-level transformations, all recorded in provenance: BFCL pseudo-schema types to JSON Schema,
dotted function names sanitized (`a.b` → `a_b`, original kept in `tool_name_map`), and a system
message, when present, kept in the state as `system_prompt`.

Gold arguments are the ground truth's per-parameter accepted values, kept verbatim as
`ExpectedOutcome.argument_options` (`""` = may be omitted) and scored by `eval/argmatch.py`.
Grounding rules come only from those values: an accepted scalar at any depth that the
deterministic checker would otherwise call unsupported (unit conversions, signs from compass
directions, ordinals, documented defaults) becomes a `fixture_default` for that path. No rule
introduces a value absent from the source. Items whose first accepted call violates their own
schema are kept and tagged `gold_schema_inconsistent` (errors in `provenance.gold_schema_errors`);
items whose ground truth accepts a placeholder-like value (BFCL uses `"N/A"` as a gold value for
some `unit` parameters) are kept and tagged `gold_contains_placeholder`.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from rlcdselect.core.types import ExpectedOutcome, Task, ToolRole, ToolSpec
from rlcdselect.datasets.external.common import (
    BFCL_ANSWERLESS_SUBSETS,
    BFCL_INCLUDED_SUBSETS,
    SOURCES,
    AdapterResult,
    Exclusion,
    Skip,
    check_schema,
    normalize_schema,
    provenance,
    read_json_or_jsonl,
    sanitize_names,
    sha256_file,
)
from rlcdselect.core.placeholders import DEFAULT_DETECTOR
from rlcdselect.eval.argmatch import canonical_call, empty_alternative_paths, option_leaves
from rlcdselect.eval.grounding import DEFAULT_CHECKER
from rlcdselect.execution.mock import schema_errors

ADAPTER_VERSION = "bfcl_v1"
SERVER_ID = "bfcl"


def _state(question: Any) -> tuple[dict[str, Any], set[str]]:
    if not isinstance(question, list) or len(question) != 1 or not isinstance(question[0], list):
        raise Skip("multi_turn", f"{len(question) if isinstance(question, list) else '?'} turns")
    messages = question[0]
    roles = [m.get("role") for m in messages]
    if any(r not in ("user", "system") for r in roles):
        raise Skip("conversation_history", ",".join(map(str, roles)))
    users = [m["content"] for m in messages if m.get("role") == "user"]
    if len(users) != 1:
        raise Skip("multiple_user_messages" if users else "no_user_message", str(len(users)))
    systems = [m["content"] for m in messages if m.get("role") == "system"]
    if systems:
        return {"system_prompt": "\n\n".join(systems), "user_request": users[0]}, {"system_message_in_state"}
    return {"user_request": users[0]}, set()


def _grounding_rules(options: Mapping[str, Any], state: Mapping[str, Any]) -> dict | None:
    """Permitted defaults from the ground truth only: every accepted scalar (at any depth) that the
    deterministic checker would otherwise call unsupported. The gold annotation is the source's own
    statement that the value follows from the request, e.g. 40% -> 0.4, "112.07 W" -> -112.07,
    "2nd and 3rd floors" -> [2, 3], or a documented default the request never states."""
    rules: dict[str, dict[str, Any]] = {}
    for path, value in option_leaves(options):
        if isinstance(value, bool) or value is None:
            continue
        status = DEFAULT_CHECKER.check({"v": value}, None, state).get("v", {}).get("status")
        if status == "unsupported":
            entry = rules.setdefault(path, {"fixture_defaults": [], "origin": "bfcl_possible_answer"})
            if value not in entry["fixture_defaults"]:
                entry["fixture_defaults"].append(value)
    return rules or None


def adapt_row(row: Mapping[str, Any], subset: str, answers: Mapping[str, Any]) -> Task:
    if subset not in BFCL_INCLUDED_SUBSETS:
        raise Skip("subset_not_adapted", subset)
    state, transformations = _state(row.get("question"))
    functions = row.get("function") or []
    if not functions:
        raise Skip("no_candidate_tools")
    names = [f.get("name") for f in functions]
    name_map = sanitize_names(names, transformations)
    specs, schemas = [], {}
    for f in functions:
        schema = normalize_schema(f.get("parameters") or {"type": "object", "properties": {}}, transformations)
        check_schema(schema)
        spec = ToolSpec(SERVER_ID, name_map[f["name"]], f.get("description") or "", schema)
        specs.append(spec)
        schemas[f["name"]] = schema
    roles = {s.key: ToolRole.IRRELEVANT for s in specs}
    gold_name, options, rules, gold_schema_errors, gold_placeholders = None, None, None, None, None
    gold_empty_alternatives = None

    if subset in ("irrelevance", "live_irrelevance"):
        expected = ExpectedOutcome(frozenset(), abstain_reason="no_suitable_tool")
        label = "irrelevance"
    elif subset == "live_relevance":
        if len(functions) != 1:
            raise Skip("relevance_gold_function_ambiguous", f"{len(functions)} functions")
        gold_name, label = names[0], "relevance"
    else:
        answer = answers.get(row["id"])
        if answer is None:
            raise Skip("no_ground_truth")
        truth = answer.get("ground_truth") or []
        if len(truth) != 1 or not isinstance(truth[0], Mapping) or len(truth[0]) != 1:
            raise Skip("multiple_calls_in_ground_truth", str(len(truth)))
        gold_name, options = next(iter(truth[0].items()))
        if gold_name not in name_map:
            raise Skip("ground_truth_function_not_in_candidates", str(gold_name))
        rules = _grounding_rules(options, state)
        gold_call = canonical_call(options)
        gold_schema_errors = list(schema_errors(schemas[gold_name], gold_call))
        gold_placeholders = list(DEFAULT_DETECTOR.paths(gold_call))
        gold_empty_alternatives = empty_alternative_paths(options)
        label = "call"
    if gold_name is not None:
        gold_key = f"{SERVER_ID}/{name_map[gold_name]}"
        roles[gold_key] = ToolRole.TRUSTED
        expected = ExpectedOutcome(frozenset({gold_key}), argument_options=options)

    return Task(
        task_id=f"bfcl:{row['id']}",
        state=state,
        tools=tuple(specs),
        expected=expected,
        roles=roles,
        tags=("bfcl", f"bfcl:{subset}", "no_suitable_tool" if label == "irrelevance" else "clean")
             + (("gold_schema_inconsistent",) if gold_schema_errors else ())
             + (("gold_contains_placeholder",) if gold_placeholders else ())
             + (("gold_empty_alternative",) if gold_empty_alternatives else ()),
        argument_grounding=rules,
        provenance=provenance(
            source=SOURCES[f"bfcl/{subset}"], split=subset, item_id=row["id"], adapter_version=ADAPTER_VERSION,
            transformations=transformations, source_tool_order=names, name_map=name_map, source_label=label,
            source_gold_function=gold_name,
            # The ground truth's first accepted call violates the source's own schema (kept, flagged).
            gold_schema_errors=gold_schema_errors or None,
            # The ground truth itself accepts a placeholder-like value (e.g. unit "N/A"), which the
            # project's grounding policy treats as a hard failure. Kept and flagged, not reconciled.
            gold_placeholder_paths=gold_placeholders or None,
            # Parameters whose accepted-value list is empty (`[]`): BFCL does not document the
            # meaning; `argmatch` reads it as "omit or empty", an interpretation.
            gold_empty_alternative_paths=gold_empty_alternatives or None,
            answers_file=SOURCES[f"bfcl/{subset}/answers"].path if subset not in BFCL_ANSWERLESS_SUBSETS else None,
        ),
    )


def adapt(rows: Iterable[Mapping[str, Any]], subset: str, answers: Iterable[Mapping[str, Any]] = (), *,
          source_sha256: str | None = None) -> AdapterResult:
    by_id = {a["id"]: a for a in answers}
    tasks, exclusions, n = [], [], 0
    for row in rows:
        n += 1
        try:
            tasks.append(adapt_row(row, subset, by_id))
        except Skip as skip:
            exclusions.append(Exclusion("bfcl", subset, str(row.get("id", n - 1)), skip.reason, skip.detail))
    src = SOURCES.get(f"bfcl/{subset}")
    return AdapterResult("bfcl", ADAPTER_VERSION, tuple(tasks), tuple(exclusions), n,
                         {"repo": src.repo if src else None, "commit": src.commit if src else None,
                          "file": src.path if src else None, "subset": subset, "sha256": source_sha256})


def load(subset: str, root: Path | None = None) -> AdapterResult:
    src = SOURCES[f"bfcl/{subset}"]
    path = src.local_path(root) if root else src.local_path()
    answers = []
    if subset not in BFCL_ANSWERLESS_SUBSETS:
        a = SOURCES[f"bfcl/{subset}/answers"]
        answers = read_json_or_jsonl(a.local_path(root) if root else a.local_path())
    return adapt(read_json_or_jsonl(path), subset, answers, source_sha256=sha256_file(path))
