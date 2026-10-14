"""Deep freezing and canonical JSON.

Tool metadata and task state are deep-frozen on construction so that no pipeline, selector, or
perturbation can mutate a fixture in place. `thaw` turns frozen values back into plain JSON values
for serialization, and `canonical_json` gives byte-stable output for hashing and snapshots.
"""

import dataclasses
import enum
import hashlib
import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze(value: Any) -> Any:
    """Recursively convert dicts to read-only mappings and lists to tuples."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    """Recursively convert frozen or dataclass values into plain JSON-compatible values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: thaw(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, frozenset, set)):
        items = [thaw(v) for v in value]
        if isinstance(value, (frozenset, set)):
            items.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return items
    if isinstance(value, float) and not math.isfinite(value):
        # Keep non-finite numbers visible instead of emitting invalid JSON.
        return repr(value)
    return value


def canonical_json(value: Any) -> str:
    """Serialize to compact JSON with sorted keys, suitable for hashing and snapshots."""
    return json.dumps(thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
