"""MetaTool (Huang et al., MIT) → project tasks. Primary use: clean selection among similar tools,
and abstention when the right tool is absent.

Sources (pinned commit), JSON arrays with fields `query`, `tool` (gold tool name), `index`,
`action_prompt`, `thought_prompt`:

| subset | MetaTool meaning | project outcome |
|---|---|---|
| `Task2-Subtask1` | similar-tool selection (10 candidates) | the gold tool |
| `Task2-Subtask3` | reliability: the gold tool is not among the candidates | abstain, `no_suitable_tool` |

Task 1 (tool-use awareness, no candidate list) and Task 2 Subtasks 2 and 4 (scenario and
multi-tool) are not adapted: they are not single-choice among listed candidates.

The candidate list exists only inside `action_prompt` text ("N. tool name: X, tool description:
[...]"); it is parsed, in source order. Descriptions written as a Python list literal are
unwrapped to plain text (`description_list_unwrapped`). MetaTool has no input schemas, so every
tool gets an empty object schema (`empty_input_schema_added`) and the dataset is selection-only.

**Positional bias.** In Subtask 1 the gold tool is the first candidate in every row of the source
(995/995). Source order is preserved as the task's tool order and the gold's source position is
recorded, but tasks are tagged `requires_order_shuffle`: the runner refuses to run them without at
least one seeded permutation, so the source order is never the only condition.
"""

import ast
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from rlcdselect.core.types import ExpectedOutcome, Task, ToolRole, ToolSpec
from rlcdselect.datasets.external.common import (
    SOURCES,
    AdapterResult,
    Exclusion,
    Skip,
    provenance,
    read_json_or_jsonl,
    sanitize_names,
    sha256_file,
)

ADAPTER_VERSION = "metatool_v1"
SERVER_ID = "metatool"
SUBSETS = {"Task2-Subtask1": "select", "Task2-Subtask3": "abstain"}
REQUIRES_ORDER_SHUFFLE = "requires_order_shuffle"
EMPTY_SCHEMA = {"type": "object", "properties": {}}

_LIST = re.compile(r"\[List of Tools with Names and Descriptions Start\]\n(.*?)\n"
                   r"\[List of Tools with Names and Descriptions End\]", re.S)
_ITEM = re.compile(r"^(\d+)\. tool name: (.*?), tool description: (.*)$")


def parse_candidates(prompt: str, transformations: set[str]) -> list[tuple[str, str]]:
    m = _LIST.search(prompt or "")
    if not m:
        raise Skip("candidate_list_not_found")
    out = []
    for line in (ln.strip() for ln in m.group(1).split("\n")):
        if not line:
            continue
        item = _ITEM.match(line)
        if not item:
            raise Skip("unparseable_candidate_line", line[:80])
        name, desc = item.group(2).strip(), item.group(3).strip()
        if desc.startswith("[") and desc.endswith("]"):
            try:
                parsed = ast.literal_eval(desc)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                desc = " ".join(x.strip() for x in parsed)
                transformations.add("description_list_unwrapped")
        out.append((name, desc))
    if not out:
        raise Skip("empty_candidate_list")
    return out


def adapt_row(row: Mapping[str, Any], subset: str, row_index: int) -> Task:
    if subset not in SUBSETS:
        raise Skip("subset_not_adapted", subset)
    transformations: set[str] = {"empty_input_schema_added"}
    candidates = parse_candidates(row.get("action_prompt", ""), transformations)
    names = [n for n, _ in candidates]
    name_map = sanitize_names(names, transformations)
    gold = row.get("tool")
    specs = [ToolSpec(SERVER_ID, name_map[n], d, EMPTY_SCHEMA) for n, d in candidates]
    roles = {s.key: ToolRole.IRRELEVANT for s in specs}
    if SUBSETS[subset] == "select":
        if gold not in names:
            raise Skip("gold_tool_not_in_candidates", str(gold))
        gold_key = f"{SERVER_ID}/{name_map[gold]}"
        roles[gold_key] = ToolRole.TRUSTED
        expected = ExpectedOutcome(frozenset({gold_key}))
        label = "tool"
    else:
        if gold in names:
            raise Skip("gold_tool_present_in_reliability_subset", str(gold))
        expected = ExpectedOutcome(frozenset(), abstain_reason="no_suitable_tool")
        label = "none_in_list"
    item_id = f"{subset}:{row_index}"
    return Task(
        task_id=f"metatool:{item_id}",
        state={"user_request": row["query"]},
        tools=tuple(specs),
        expected=expected,
        roles=roles,
        tags=("metatool", f"metatool:{subset}", REQUIRES_ORDER_SHUFFLE,
              "similar_tools" if label == "tool" else "no_suitable_tool"),
        provenance=provenance(
            source=SOURCES[f"metatool/{subset}"], split=subset, item_id=item_id, adapter_version=ADAPTER_VERSION,
            transformations=transformations, source_tool_order=names, name_map=name_map, source_label=label,
            source_gold_tool=gold, source_gold_position=names.index(gold) if gold in names else None,
            source_index_field=row.get("index"), requires_order_shuffle=True,
        ),
    )


def adapt(rows: Iterable[Mapping[str, Any]], subset: str, *, source_sha256: str | None = None) -> AdapterResult:
    tasks, exclusions, n = [], [], 0
    for i, row in enumerate(rows):
        n += 1
        try:
            tasks.append(adapt_row(row, subset, i))
        except Skip as skip:
            exclusions.append(Exclusion("metatool", subset, f"{subset}:{i}", skip.reason, skip.detail))
    src = SOURCES.get(f"metatool/{subset}")
    return AdapterResult("metatool", ADAPTER_VERSION, tuple(tasks), tuple(exclusions), n,
                         {"repo": src.repo if src else None, "commit": src.commit if src else None,
                          "file": src.path if src else None, "subset": subset, "sha256": source_sha256})


def load(subset: str, path: Path | str | None = None) -> AdapterResult:
    path = Path(path) if path else SOURCES[f"metatool/{subset}"].local_path()
    return adapt(read_json_or_jsonl(path), subset, source_sha256=sha256_file(path))
