import json
import pytest
from dataclasses import asdict
from inverted.tasks import generate_task


@pytest.mark.parametrize("family", ["state", "policy", "reconciliation"])
def test_generation_is_deterministic(family):
    a = generate_task(family, 3, 123)
    b = generate_task(family, 3, 123)
    assert json.dumps(asdict(a), sort_keys=True, default=str) == json.dumps(asdict(b), sort_keys=True, default=str)


def test_different_seeds_vary_tasks():
    assert generate_task("state", 2, 1).id != generate_task("state", 2, 2).id


@pytest.mark.parametrize("level,lo,hi", [(1,1,2),(2,3,5),(3,6,9),(4,10,15)])
def test_complexity_requirement_ranges(level, lo, hi):
    task = generate_task("state", level, 44)
    assert lo <= len(task.requirements) <= hi


@pytest.mark.parametrize("family", ["state", "policy", "reconciliation"])
def test_all_families_have_machine_checkable_requirements(family):
    task = generate_task(family, 2, 99)
    assert task.family == family
    assert task.requirements
    assert task.target_state != task.initial_state

def test_public_information_is_symmetric_and_contains_no_hidden_action_plan():
    task = generate_task("policy", 3, 1234)
    assert "correct_actions" not in task.metadata
    public = task.metadata["public_requirements"]
    assert len(public) == len(task.requirements)
    assert all("critical" not in item for item in public)
