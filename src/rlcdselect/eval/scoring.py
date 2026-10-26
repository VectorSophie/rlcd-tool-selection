"""Per-run scoring. Selection, arguments, grounding, execution and task success are scored separately.

`task_success` keeps its original definition. `grounded_task_success` is the stricter metric
intended for future primary analysis: it also requires the generated arguments to have no hard
grounding failure (no placeholder, no unsupported required or fixture-critical value; see
`eval/grounding.py`). `grounded_task_success_strict` keeps the earlier rule, under which any
unsupported value, optional ones included, fails.
"""

from typing import Any

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.types import ABSTAIN, ArgumentStatus, SelectionStatus, Task
from rlcdselect.eval.argmatch import options_mismatches
from rlcdselect.eval.grounding import ground_arguments, grounded_task_success, grounding_summary
from rlcdselect.pipelines.base import PipelineOutcome


def selection_label(outcome: PipelineOutcome) -> str | None:
    """The discrete outcome used by primary metrics: a tool key, ABSTAIN, or None for failures."""
    sel = outcome.selection
    if sel.status is SelectionStatus.SELECTED:
        return sel.selected_tool_key
    if sel.status is SelectionStatus.ABSTAINED:
        return ABSTAIN
    return None


def score(task: Task, outcome: PipelineOutcome) -> dict[str, Any]:
    expected = task.expected
    label = selection_label(outcome)
    if expected.expects_abstention:
        selection_correct = label == ABSTAIN
    else:
        selection_correct = label in expected.tool_keys

    args = outcome.arguments
    arguments_match = None
    argument_mismatches: list[str] | None = None
    if (expected.argument_constraints or expected.argument_options) and selection_correct \
            and not expected.expects_abstention:
        given = thaw(args.arguments) if args.status is ArgumentStatus.OK else {}
        argument_mismatches = [f"{k}: expected {v!r}" for k, v in thaw(expected.argument_constraints or {}).items()
                               if given.get(k) != v]
        if expected.argument_options is not None:
            argument_mismatches += options_mismatches(given, thaw(expected.argument_options))
        arguments_match = not argument_mismatches

    execution_success = outcome.execution.success if outcome.execution is not None else None
    if expected.expects_abstention:
        task_success = selection_correct
    else:
        task_success = selection_correct and execution_success is True and arguments_match is not False

    provenance = None
    if args.status is ArgumentStatus.OK and args.arguments is not None:
        tool = next((t for t in task.tools if t.key == outcome.selection.selected_tool_key), None)
        provenance = ground_arguments(args.arguments, tool.input_schema if tool else None, task.state,
                                      task.argument_grounding, context=task.evaluation_context)
    grounding = grounding_summary(provenance)

    role = None
    if label == ABSTAIN:
        role = "abstain"
    elif label is not None:
        role = task.roles[label].value

    return {
        "selection_label": label,
        "selected_role": role,
        "abstention_expected": expected.expects_abstention,
        "selection_correct": selection_correct,
        "abstention_correct": (label == ABSTAIN) if expected.expects_abstention else None,
        "selector_error": outcome.selection.status in (SelectionStatus.ERROR, SelectionStatus.MULTIPLE),
        "argument_error": args.status is ArgumentStatus.ERROR,
        "arguments_schema_valid": args.schema_valid,
        "arguments_match": arguments_match,
        "argument_mismatches": argument_mismatches,
        "execution_success": execution_success,
        "task_success": task_success,
        # Grounding-aware fields (record schema v3). The original arguments are left untouched.
        "argument_provenance": provenance,
        **grounding,
        "grounded_task_success": grounded_task_success(task_success, expected.expects_abstention,
                                                       grounding["argument_grounding_ok"]),
        "grounded_task_success_strict": grounded_task_success(task_success, expected.expects_abstention,
                                                              grounding["argument_grounding_ok_strict"]),
    }
