"""Shared pieces for external dataset adapters: pinned sources, provenance, exclusions, and the
explicit (logged) transformations every adapter may need.

Transformations are never silent. Each task's `provenance["transformations"]` lists every change
made to the source item, and the original values are kept in provenance (e.g. `tool_name_map`).
"""

import hashlib
import json
import re
import urllib.request
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from rlcdselect.core.types import Task

DATA_ROOT = Path("data/external")
FUNCTION_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # what native function calling accepts


@dataclass(frozen=True)
class SourceFile:
    dataset: str
    repo: str
    commit: str
    path: str
    license: str

    @property
    def url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.commit}/{self.path}"

    def local_path(self, root: Path = DATA_ROOT) -> Path:
        return root / self.dataset / self.commit[:12] / self.path


WHEN2CALL_COMMIT = "ecc8d42388e91ab37e7e737d48e16e8ecea3d1dc"
METATOOL_COMMIT = "35e81bb7576826e980c80fed8f8c0a2b4a1e6fbb"
BFCL_COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
_BFCL_DIR = "berkeley-function-call-leaderboard/bfcl_eval/data"

SOURCES: dict[str, SourceFile] = {
    "when2call/test_mcq": SourceFile("when2call", "NVIDIA/When2Call", WHEN2CALL_COMMIT,
                                     "data/test/when2call_test_mcq.jsonl", "Apache-2.0"),
    "metatool/Task2-Subtask1": SourceFile("metatool", "HowieHwong/MetaTool", METATOOL_COMMIT,
                                          "dataset/tmp_dataset/Task2-Subtask1.json", "MIT"),
    "metatool/Task2-Subtask3": SourceFile("metatool", "HowieHwong/MetaTool", METATOOL_COMMIT,
                                          "dataset/tmp_dataset/Task2-Subtask3.json", "MIT"),
}
BFCL_INCLUDED_SUBSETS = ("simple_python", "multiple", "live_simple", "live_multiple", "irrelevance",
                         "live_irrelevance", "live_relevance")
BFCL_ANSWERLESS_SUBSETS = ("irrelevance", "live_irrelevance", "live_relevance")
# Subsets not adapted, and why (they do not fit a single-choice, single-call, stateless harness).
BFCL_EXCLUDED_SUBSETS = {
    "parallel": "several calls per item", "parallel_multiple": "several calls per item",
    "live_parallel": "several calls per item", "live_parallel_multiple": "several calls per item",
    "multi_turn_base": "multi-turn, stateful", "multi_turn_long_context": "multi-turn, stateful",
    "multi_turn_miss_func": "multi-turn, stateful", "multi_turn_miss_param": "multi-turn, stateful",
    "memory": "stateful memory backend", "web_search": "multi-step, live web",
    "simple_java": "Java-typed schemas", "simple_javascript": "JavaScript-typed schemas",
    "format_sensitivity": "prompt-format study, not selection",
}
for _subset in BFCL_INCLUDED_SUBSETS:
    SOURCES[f"bfcl/{_subset}"] = SourceFile("bfcl", "ShishirPatil/gorilla", BFCL_COMMIT,
                                            f"{_BFCL_DIR}/BFCL_v4_{_subset}.json", "Apache-2.0")
    if _subset not in BFCL_ANSWERLESS_SUBSETS:
        SOURCES[f"bfcl/{_subset}/answers"] = SourceFile("bfcl", "ShishirPatil/gorilla", BFCL_COMMIT,
                                                        f"{_BFCL_DIR}/possible_answer/BFCL_v4_{_subset}.json",
                                                        "Apache-2.0")


def fetch(source: SourceFile, root: Path = DATA_ROOT, *, force: bool = False) -> tuple[Path, str]:
    """Download one pinned source file (documented upstream raw URL) into `root`. Returns the path
    and its SHA-256. Network access happens only here, only when called explicitly."""
    path = source.local_path(root)
    if force or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(source.url, timeout=120) as resp:  # noqa: S310 (pinned https URL)
            path.write_bytes(resp.read())
    return path, sha256_file(path)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json_or_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """BFCL files are JSON Lines despite the .json extension; MetaTool files are JSON arrays."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# --- exclusions and results --------------------------------------------------------------------

@dataclass(frozen=True)
class Exclusion:
    source_dataset: str
    source_split: str
    source_item_id: str
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class AdapterResult:
    dataset: str
    adapter_version: str
    tasks: tuple[Task, ...]
    exclusions: tuple[Exclusion, ...]
    source_rows: int
    source: Mapping[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        labels = Counter((t.provenance or {}).get("source_label") for t in self.tasks)
        return {
            "dataset": self.dataset, "adapter_version": self.adapter_version, "source": dict(self.source),
            "source_rows": self.source_rows, "included": len(self.tasks), "excluded": len(self.exclusions),
            "included_by_source_label": dict(sorted((str(k), v) for k, v in labels.items())),
            "exclusion_reasons": dict(Counter(e.reason for e in self.exclusions).most_common()),
        }


class Skip(Exception):
    """Raised inside an adapter to exclude the current row with a reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason, self.detail = reason, detail


# --- logged transformations --------------------------------------------------------------------

_BFCL_TYPE_MAP = {"dict": "object", "float": "number", "tuple": "array"}
_JSON_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def normalize_schema(schema: Any, transformations: set[str]) -> Any:
    """BFCL-style pseudo-schemas to JSON Schema: `dict`→`object`, `float`→`number`,
    `tuple`→`array`, `any`→ no type constraint. Any other non-JSON-Schema type raises `Skip`.
    Key order is preserved; every rewrite is recorded in `transformations`."""
    if isinstance(schema, Mapping):
        out = {}
        for k, v in schema.items():
            if k == "type" and isinstance(v, str):
                if v in _BFCL_TYPE_MAP:
                    transformations.add(f"schema_type_{v}_to_{_BFCL_TYPE_MAP[v]}")
                    out[k] = _BFCL_TYPE_MAP[v]
                elif v == "any":
                    transformations.add("schema_type_any_removed")
                elif v in _JSON_TYPES:
                    out[k] = v
                else:
                    raise Skip("unsupported_schema_type", v)
            elif k in ("properties",) and isinstance(v, Mapping):
                out[k] = {pk: normalize_schema(pv, transformations) for pk, pv in v.items()}
            else:
                out[k] = normalize_schema(v, transformations)
        return out
    if isinstance(schema, list):
        return [normalize_schema(v, transformations) for v in schema]
    return schema


def check_schema(schema: Mapping[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise Skip("invalid_json_schema", exc.message) from exc


def sanitize_names(names: Sequence[str], transformations: set[str]) -> dict[str, str]:
    """Map original tool names to valid function names (`[A-Za-z0-9_-]{1,64}`), replacing every
    other character with `_`. Duplicate originals or a collision after sanitizing raise `Skip`;
    names are never silently merged."""
    if len(set(names)) != len(names):
        raise Skip("duplicate_tool_names", ", ".join(sorted(n for n in set(names) if names.count(n) > 1)))
    mapping = {}
    for name in names:
        clean = re.sub(r"[^A-Za-z0-9_-]", "_", name)
        if not FUNCTION_NAME_RE.match(clean):
            raise Skip("invalid_function_name", name)
        if clean != name:
            transformations.add("tool_name_sanitized")
        mapping[name] = clean
    if len(set(mapping.values())) != len(mapping):
        raise Skip("name_collision_after_sanitization", ", ".join(names))
    return mapping


def provenance(*, source: SourceFile, split: str, item_id: str, adapter_version: str, transformations: Iterable[str],
               source_tool_order: Sequence[str], name_map: Mapping[str, str], source_label: Any, **extra: Any) -> dict:
    return {
        "source_dataset": source.dataset,
        "source_repo": source.repo,
        "source_split": split,
        "source_item_id": item_id,
        "source_version_or_commit": source.commit,
        "source_file": source.path,
        "source_license": source.license,
        "adapter_version": adapter_version,
        "transformations": sorted(transformations),
        "source_label": source_label,
        "source_tool_order": list(source_tool_order),  # original names, in source order
        "tool_name_map": dict(name_map),  # original -> presented
        **extra,
    }
