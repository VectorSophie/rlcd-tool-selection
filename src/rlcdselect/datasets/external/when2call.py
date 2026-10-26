"""When2Call (NVIDIA, Apache-2.0) → project tasks. Primary use: whether a tool should be called.

Source: `data/test/when2call_test_mcq.jsonl` at the pinned commit. Each row has a question, a list
of tool definitions (BFCL-style pseudo-schemas, as JSON strings), the correct behaviour
(`correct_answer`) and, for tool rows, `target_tool`. The source also defines a `direct` answer
option, but no test row has it as the correct answer.

Label mapping (the source label is always kept in `provenance.source_label`):

| source label | project outcome | `abstain_reason` | roles |
|---|---|---|---|
| `tool_call` | the target tool | none | target = trusted, others = irrelevant |
| `request_for_info` | abstain | `missing_information` | target = trusted (right tool, info missing), others = irrelevant |
| `cannot_answer` | abstain | `no_suitable_tool` | all irrelevant (the target tool was removed upstream) |

`request_for_info` and `cannot_answer` both expect no tool call, but are never merged: their
`abstain_reason` differs and the original label is preserved.

Not scored as gold arguments: the `tool_call` answer text is a single reference call written for
the MCQ (no accepted alternatives). It is kept in provenance as `reference_arguments`.

Exclusions (one reason each, deterministic order): `no_candidate_tools`, `unparseable_tool`,
`target_tool_not_in_candidates`, `unknown_source_label`, plus the shared name and schema checks.
The three labels are variants of one upstream item (`source_id`, recorded as `source_group_id`);
analyses should treat each group as a cluster.
"""

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from rlcdselect.core.types import ExpectedOutcome, Task, ToolRole, ToolSpec
from rlcdselect.datasets.external.common import (
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

ADAPTER_VERSION = "when2call_v1"
SERVER_ID = "when2call"
SOURCE = SOURCES["when2call/test_mcq"]
LABELS = {
    "tool_call": None,
    "request_for_info": "missing_information",
    "cannot_answer": "no_suitable_tool",
}


def adapt_row(row: Mapping[str, Any], split: str = "test_mcq") -> Task:
    label = row.get("correct_answer")
    if label not in LABELS:
        raise Skip("unknown_source_label", str(label))
    try:
        tools = [json.loads(t) if isinstance(t, str) else dict(t) for t in row.get("tools") or []]
        target = json.loads(row["target_tool"]) if isinstance(row.get("target_tool"), str) else row.get("target_tool")
    except (json.JSONDecodeError, TypeError) as exc:
        raise Skip("unparseable_tool", str(exc)) from exc
    if not tools:
        raise Skip("no_candidate_tools", label)
    names = [t.get("name") for t in tools]
    if not all(isinstance(n, str) and n for n in names):
        raise Skip("unparseable_tool", "tool without a name")
    target_name = (target or {}).get("name")
    if label != "cannot_answer" and target_name not in names:
        raise Skip("target_tool_not_in_candidates", str(target_name))

    transformations: set[str] = set()
    name_map = sanitize_names(names, transformations)
    specs = []
    for t in tools:
        schema = normalize_schema(t.get("parameters") or {"type": "object", "properties": {}}, transformations)
        check_schema(schema)
        specs.append(ToolSpec(SERVER_ID, name_map[t["name"]], t.get("description") or "", schema))

    key_of = {orig: f"{SERVER_ID}/{new}" for orig, new in name_map.items()}
    target_key = key_of.get(target_name)
    roles = {s.key: ToolRole.IRRELEVANT for s in specs}
    if label in ("tool_call", "request_for_info"):
        roles[target_key] = ToolRole.TRUSTED
    expected = (ExpectedOutcome(frozenset({target_key})) if label == "tool_call"
                else ExpectedOutcome(frozenset(), abstain_reason=LABELS[label]))

    reference = None
    answer = (row.get("answers") or {}).get("tool_call")
    if label == "tool_call" and isinstance(answer, str):
        try:
            reference = json.loads(answer).get("arguments")
        except (json.JSONDecodeError, AttributeError):
            reference = None
    return Task(
        task_id=f"when2call:{row['uuid']}",
        state={"user_request": row["question"]},
        tools=tuple(specs),
        expected=expected,
        roles=roles,
        tags=("when2call", f"when2call:{label}", "missing_information" if label == "request_for_info"
              else "no_suitable_tool" if label == "cannot_answer" else "clean"),
        provenance=provenance(
            source=SOURCE, split=split, item_id=row["uuid"], adapter_version=ADAPTER_VERSION,
            transformations=transformations, source_tool_order=names, name_map=name_map, source_label=label,
            source_group_id=row.get("source_id"), source_origin=row.get("source"),
            source_target_tool=target_name, held_out_param=row.get("held_out_param"),
            reference_arguments=reference,
        ),
    )


def adapt(rows: Iterable[Mapping[str, Any]], *, split: str = "test_mcq", source_sha256: str | None = None) -> AdapterResult:
    tasks, exclusions, n = [], [], 0
    for row in rows:
        n += 1
        item = str(row.get("uuid", f"row{n - 1}"))
        try:
            tasks.append(adapt_row(row, split))
        except Skip as skip:
            exclusions.append(Exclusion("when2call", split, item, skip.reason, skip.detail))
    return AdapterResult("when2call", ADAPTER_VERSION, tuple(tasks), tuple(exclusions), n,
                         {"repo": SOURCE.repo, "commit": SOURCE.commit, "file": SOURCE.path, "sha256": source_sha256})


def load(path: Path | str | None = None) -> AdapterResult:
    path = Path(path) if path else SOURCE.local_path()
    return adapt(read_json_or_jsonl(path), source_sha256=sha256_file(path))
