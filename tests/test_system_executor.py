from inverted.oracle import evaluate_task
from inverted.system_executor import generate_candidate
from inverted.tasks import generate_task


def test_candidate_generation_is_seeded():
    task = generate_task("state", 3, 5)
    a = generate_candidate(task, 0.6, 11)
    b = generate_candidate(task, 0.6, 11)
    assert a == b


def test_quality_extremes_control_correctness():
    task = generate_task("state", 3, 8)
    good = generate_candidate(task, 1.0, 42)
    bad = generate_candidate(task, 0.0, 42)
    assert evaluate_task(task, good.state, good.actions).success is True
    assert evaluate_task(task, bad.state, bad.actions).success is False
    assert bad.injected_faults


def test_bad_candidate_remains_structurally_legal():
    task = generate_task("policy", 4, 12)
    candidate = generate_candidate(task, 0.0, 77)
    assert all(a.op in task.allowed_ops for a in candidate.actions)
