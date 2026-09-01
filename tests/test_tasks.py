import json
from dataclasses import asdict

import pytest

from inverted.oracle import evaluate_task
from inverted.tasks import generate_task


ALL_FAMILIES = (
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
)


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_generation_is_deterministic(family):
    a = generate_task(family, 3, 123)
    b = generate_task(family, 3, 123)
    assert json.dumps(asdict(a), sort_keys=True, default=str) == json.dumps(asdict(b), sort_keys=True, default=str)


def test_different_seeds_vary_tasks():
    assert generate_task("state", 2, 1).id != generate_task("state", 2, 2).id


@pytest.mark.parametrize("level,lo,hi", [(1, 1, 2), (2, 3, 5), (3, 6, 9), (4, 10, 15)])
def test_complexity_requirement_ranges(level, lo, hi):
    task = generate_task("state", level, 44)
    assert lo <= len(task.requirements) <= hi


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_all_families_have_machine_checkable_requirements(family):
    task = generate_task(family, 2, 99)
    assert task.family == family
    assert task.requirements
    assert task.target_state != task.initial_state


@pytest.mark.parametrize("family", ALL_FAMILIES)
def test_generated_target_satisfies_its_requirements(family):
    task = generate_task(family, 4, 44004)
    public_actions = tuple(task.metadata["solution_actions"])
    result = evaluate_task(task, task.target_state, public_actions)
    assert result.success is True


def test_public_information_is_symmetric_and_contains_no_hidden_action_plan():
    task = generate_task("policy", 3, 1234)
    assert "correct_actions" not in task.metadata
    public = task.metadata["public_requirements"]
    assert len(public) == len(task.requirements)
    assert all("critical" not in item for item in public)


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_preservation_family_has_public_preserve_invariant(level):
    task = generate_task("preservation", level, 611687 + level)
    assert any(req.kind == "preserve" for req in task.requirements)
    assert any(req.kind == "equal" for req in task.requirements)
    public = task.metadata["public_requirements"]
    assert any(row["kind"] == "preserve" for row in public)
    assert all("critical" not in row for row in public)


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_dependency_order_family_exposes_public_prerequisite_and_dependent_actions(level):
    task = generate_task("dependency_order", level, 611916 + level)
    assert "grant" in task.allowed_ops
    assert "start" in task.allowed_ops
    assert any(req.kind == "action_before" and req.path == "grant" and req.expected == "start" for req in task.requirements)
    assert any(req.kind == "action_present" and req.path == "start" for req in task.requirements)


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_repair_containment_family_has_mutable_and_protected_requirements(level):
    task = generate_task("repair_containment", level, 612145 + level)
    equal_count = sum(req.kind == "equal" for req in task.requirements)
    assert equal_count >= 2
    assert any(req.kind == "preserve" for req in task.requirements)
    assert set(task.allowed_ops).issubset({"set", "delete"})
