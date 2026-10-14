import json
import os
from pathlib import Path

import pytest

from rlcdselect.core.jsonutil import thaw
from rlcdselect.core.serialization import (
    ABSTAIN_ID,
    CriteriaFormat,
    NamePolicy,
    Representation,
    SerializationConfig,
    SerializationError,
    build_native_tools,
    build_selector_request,
    present_candidates,
    present_task,
)
from rlcdselect.core.types import ToolSpec
from rlcdselect.profiles import (
    ARCHITECTURE_MATCHED_V1,
    DUPLICATE_NAME_STRESS_V1,
    ECOLOGICAL_NAME_DESCRIPTION_V1,
)

SNAPSHOTS = Path(__file__).parent / "snapshots"


def test_order_is_deterministic_under_seed(tasks):  # required test 8
    task = tasks["attacker_with_decoy"]
    cfg = SerializationConfig()
    a = present_task(task, cfg, order_seed=7, id_seed=None)
    b = present_task(task, cfg, order_seed=7, id_seed=None)
    assert a == b
    orders = {present_task(task, cfg, order_seed=s, id_seed=None).tool_order for s in range(10)}
    assert len(orders) > 1  # seeds actually change the order
    assert present_task(task, cfg, order_seed=None, id_seed=None).tool_order == tuple(t.key for t in task.tools)


def test_ids_are_independent_of_presentation_order(tasks):
    task = tasks["attacker_with_decoy"]
    cfg = SerializationConfig()
    canonical = present_task(task, cfg, order_seed=None, id_seed=None).id_map
    for seed in range(5):
        assert present_task(task, cfg, order_seed=seed, id_seed=None).id_map == canonical
    assert canonical == {f"t{i}": t.key for i, t in enumerate(task.tools)}
    permuted = present_task(task, cfg, order_seed=None, id_seed=3).id_map
    assert sorted(permuted) == sorted(canonical) and set(permuted.values()) == set(canonical.values())


def test_ids_are_opaque_and_real_name_is_visible(tasks):
    task = tasks["obvious_search_web"]
    cfg = SerializationConfig()
    req = build_selector_request(task.state, present_task(task, cfg, order_seed=None, id_seed=None), cfg)
    assert all(cid.startswith("t") and cid[1:].isdigit() for cid in req.candidate_ids)
    assert any(isinstance(c, str) and c.startswith("search_web: ") for c in req.criteria.values())


def test_duplicate_names_are_an_error_by_default(tasks):
    task = tasks["stress_exact_name_collision"]
    with pytest.raises(SerializationError):
        present_task(task, SerializationConfig(name_policy=NamePolicy.TOOL_NAME), order_seed=None, id_seed=None)


def test_duplicate_names_allowed_only_for_decomposed_stress(tasks):
    task = tasks["stress_exact_name_collision"]
    cset = present_task(task, DUPLICATE_NAME_STRESS_V1, order_seed=None, id_seed=None)
    assert [c.display_name for c in cset.candidates].count("send_email") == 2
    req = build_selector_request(task.state, cset, DUPLICATE_NAME_STRESS_V1)
    assert len(req.candidate_ids) == 3  # distinct opaque ids despite identical visible names
    with pytest.raises(SerializationError, match="duplicate function names"):
        build_native_tools(cset)


def test_qualification_policies_remain_available(tasks):
    task = tasks["stress_exact_name_collision"]
    cset = present_task(task, SerializationConfig(name_policy=NamePolicy.QUALIFY_ON_COLLISION), order_seed=None, id_seed=None)
    assert [c.display_name for c in cset.candidates] == ["mail__send_email", "mail-relay__send_email", "create_email_draft"]
    cset = present_task(task, SerializationConfig(name_policy=NamePolicy.SERVER_QUALIFIED), order_seed=None, id_seed=None)
    assert cset.candidates[2].display_name == "mail__create_email_draft"


@pytest.mark.parametrize("rep", list(Representation))
def test_representations_contain_exactly_the_configured_fields(tasks, rep):
    task = tasks["obvious_calendar"]
    cfg = SerializationConfig(representation=rep, criteria_format=CriteriaFormat.OBJECT)
    req = build_selector_request(task.state, present_task(task, cfg, order_seed=None, id_seed=None), cfg)
    expected = {"name"} | ({"description"} if rep is not Representation.NAME_ONLY else set())
    expected |= {"input_schema"} if rep is Representation.NAME_DESCRIPTION_SCHEMA else set()
    for cid in req.candidate_ids:
        assert set(req.criteria[cid]) == expected


def test_abstain_option_is_explicit_and_last(tasks):  # part of required test 11
    task = tasks["obvious_calendar"]
    cfg = SerializationConfig()
    req = build_selector_request(task.state, present_task(task, cfg, order_seed=3, id_seed=None), cfg)
    assert req.abstain_id == ABSTAIN_ID and list(req.criteria)[-1] == ABSTAIN_ID
    no_abstain = SerializationConfig(include_abstain=False)
    req = build_selector_request(task.state, present_task(task, no_abstain, order_seed=3, id_seed=None), no_abstain)
    assert req.abstain_id is None and ABSTAIN_ID not in req.criteria


def test_native_tools_reject_invalid_function_names():
    tool = ToolSpec("s", "has space", "d", {"type": "object", "properties": {}})
    cset = present_candidates([tool], name_policy=NamePolicy.TOOL_NAME)
    with pytest.raises(SerializationError):
        build_native_tools(cset)


def test_tool_spec_is_deeply_immutable(tasks):
    tool = tasks["obvious_calendar"].tools[0]
    with pytest.raises(TypeError):
        tool.input_schema["properties"]["to"] = {}  # type: ignore[index]
    with pytest.raises(AttributeError):
        tool.name = "x"  # type: ignore[misc]


SNAPSHOT_CASES = {
    "selector_request__architecture_matched_v1": ARCHITECTURE_MATCHED_V1,
    "selector_request__ecological_name_description_v1": ECOLOGICAL_NAME_DESCRIPTION_V1,
    "selector_request__name_only__text": SerializationConfig(representation=Representation.NAME_ONLY),
    "selector_request__name_description_schema__text": SerializationConfig(
        representation=Representation.NAME_DESCRIPTION_SCHEMA),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_selector_request_snapshots(tasks, name):  # required test 18
    cfg = SNAPSHOT_CASES[name]
    out = {}
    for task_id in ("attacker_near_name_collision", "obvious_calendar"):
        task = tasks[task_id]
        req = build_selector_request(task.state, present_task(task, cfg, order_seed=11, id_seed=None), cfg)
        out[task_id] = thaw(req)
    _check_snapshot(name, out)


def test_stress_selector_request_snapshot(tasks):
    task = tasks["stress_exact_name_collision"]
    cset = present_task(task, DUPLICATE_NAME_STRESS_V1, order_seed=11, id_seed=None)
    _check_snapshot("selector_request__duplicate_name_stress_v1",
                    thaw(build_selector_request(task.state, cset, DUPLICATE_NAME_STRESS_V1)))


def test_native_tools_snapshot(tasks):
    task = tasks["attacker_near_name_collision"]
    cset = present_task(task, ARCHITECTURE_MATCHED_V1, order_seed=11, id_seed=None)
    _check_snapshot("native_tools__attacker_near_name_collision", thaw(build_native_tools(cset)))


def _check_snapshot(name: str, value) -> None:
    path = SNAPSHOTS / f"{name}.json"
    # Not key-sorted: criteria order is presentation order and must be part of the snapshot.
    text = json.dumps(thaw(value), indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"Missing snapshot {path}; run with UPDATE_SNAPSHOTS=1 and review the diff"
    assert path.read_text(encoding="utf-8") == text
