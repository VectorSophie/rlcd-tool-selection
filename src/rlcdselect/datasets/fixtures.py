"""Loader for the project-authored static fixtures."""

import json
from importlib import resources
from typing import Any

from rlcdselect.core.types import ExpectedOutcome, Task, ToolRole
from rlcdselect.registry.static import StaticToolRegistry

DEFAULT_FIXTURE = "static_v2.json"
DECOMPOSED_ONLY_TAG = "decomposed_only"


def load_fixture_data(name: str = DEFAULT_FIXTURE) -> dict[str, Any]:
    return json.loads(resources.files("rlcdselect.datasets.fixture_data").joinpath(name).read_text(encoding="utf-8"))


def load_fixtures(name: str = DEFAULT_FIXTURE) -> tuple[StaticToolRegistry, tuple[Task, ...]]:
    data = load_fixture_data(name)
    registry = StaticToolRegistry.from_dicts(data["tools"])
    tasks = []
    for t in data["tasks"]:
        exp = t["expected"]
        tasks.append(
            Task(
                task_id=t["task_id"],
                state=t["state"],
                tools=tuple(registry.get(c["key"]) for c in t["tools"]),
                expected=ExpectedOutcome(
                    tool_keys=frozenset(exp["tool_keys"]),
                    abstain_reason=exp.get("abstain_reason"),
                    argument_constraints=exp.get("argument_constraints"),
                ),
                roles={c["key"]: ToolRole(c["role"]) for c in t["tools"]},
                tags=tuple(t.get("tags", ())),
                argument_grounding=t.get("argument_grounding"),  # evaluator-only
            )
        )
    return registry, tuple(tasks)


def core_tasks(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Tasks valid for every arm (the cross-arm benchmark)."""
    return tuple(t for t in tasks if DECOMPOSED_ONLY_TAG not in t.tags)


def decomposed_only_tasks(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Stress tasks that native function calling cannot represent (e.g. exact duplicate names)."""
    return tuple(t for t in tasks if DECOMPOSED_ONLY_TAG in t.tags)
