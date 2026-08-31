from inverted.domain import Action, Requirement, TaskCase, WorldState
from inverted.oracle import apply_actions, evaluate_task


def make_task():
    initial = WorldState({"files": {"report": {"folder": "inbox", "perm": "rw"}}, "services": {"A": True}})
    reqs = (
        Requirement("r1", "equal", "files.report.folder", "archive"),
        Requirement("r2", "preserve", "files.report.perm", "rw", critical=True),
        Requirement("r3", "action_present", "move", "files.report.folder"),
        Requirement("r4", "action_absent", "delete", None, critical=True),
    )
    target = WorldState({"files": {"report": {"folder": "archive", "perm": "rw"}}, "services": {"A": True}})
    return TaskCase("t1", "state", 2, "archive report", initial, target, reqs, ("set", "move", "delete"))


def test_oracle_accepts_correct_state_and_procedure():
    task = make_task()
    actions = (Action("move", "files.report.folder", "archive"),)
    state = apply_actions(task.initial_state, actions)
    result = evaluate_task(task, state, actions)
    assert result.success is True
    assert result.failed_requirement_ids == ()
    assert result.catastrophic is False


def test_oracle_detects_omission():
    task = make_task()
    result = evaluate_task(task, task.initial_state, ())
    assert result.success is False
    assert "r1" in result.failed_requirement_ids
    assert "r3" in result.failed_requirement_ids


def test_oracle_detects_preservation_and_catastrophic_violation():
    task = make_task()
    actions = (
        Action("move", "files.report.folder", "archive"),
        Action("set", "files.report.perm", "none"),
    )
    result = evaluate_task(task, apply_actions(task.initial_state, actions), actions)
    assert "r2" in result.failed_requirement_ids
    assert result.catastrophic is True


def test_oracle_detects_forbidden_procedure():
    task = make_task()
    actions = (
        Action("move", "files.report.folder", "archive"),
        Action("delete", "services.A", None),
    )
    result = evaluate_task(task, apply_actions(task.initial_state, actions), actions)
    assert "r4" in result.failed_requirement_ids
    assert result.catastrophic is True
