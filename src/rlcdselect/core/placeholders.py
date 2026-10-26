"""Conservative detection of placeholder argument values.

A placeholder is a value a model writes when the request lacks the information, e.g. "<UNKNOWN>",
"[RECIPIENT]", "{{subject}}", "TBD", "N/A" or "???". A value counts only when the *whole* string
is a placeholder; "Use <b>bold</b> if unknown." is not one. The pattern set is configurable.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any

DEFAULT_PLACEHOLDER_PATTERNS = (
    r"<[^<>]{1,40}>",  # <UNKNOWN>, <recipient email>
    r"\[[A-Z0-9 _-]{1,40}\]",  # [RECIPIENT]
    r"\{\{[^{}]{1,40}\}\}",  # {{subject}}
    r"(?i:unknown|tbd|tba|placeholder|n/a|none provided|not provided|unspecified)",  # not "TODO": a real code-search term
    r"\?{2,}",  # ???
)


class PlaceholderDetector:
    def __init__(self, patterns: Iterable[str] = DEFAULT_PLACEHOLDER_PATTERNS) -> None:
        self.patterns = tuple(patterns)
        self._regex = re.compile("|".join(f"(?:{p})" for p in self.patterns))

    def is_placeholder(self, value: Any) -> bool:
        return isinstance(value, str) and self._regex.fullmatch(value.strip()) is not None

    def paths(self, value: Any, path: str = "") -> tuple[str, ...]:
        """Slash-separated paths of string values that are entirely a placeholder."""
        if isinstance(value, str):
            return (path or "<root>",) if self.is_placeholder(value) else ()
        if isinstance(value, Mapping):
            return tuple(p for k, v in value.items() for p in self.paths(v, f"{path}/{k}" if path else str(k)))
        if isinstance(value, (list, tuple)):
            return tuple(p for i, v in enumerate(value) for p in self.paths(v, f"{path}/{i}" if path else str(i)))
        return ()


DEFAULT_DETECTOR = PlaceholderDetector()
