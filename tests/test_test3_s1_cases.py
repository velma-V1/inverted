from dataclasses import asdict

from inverted.oracle import evaluate_task
from inverted.test2_cases import build_holdout_cases
from inverted.test3_s1_cases import build_holdout_a, build_holdout_a_r1, build_seed_failure


def test_holdout_a_is_deterministic_balanced_and_disjoint_from_test2_holdout():
    first = build_holdout_a()
    second = build_holdout_a()
    assert [case.case_id for case in first] == [case.case_id for case in second]
    assert len(first) == 12
    assert {(case.task.family, case.task.complexity) for case in first} == {
        (family, complexity)
        for family in ("state", "policy", "reconciliation")
        for complexity in (1, 2, 3, 4)
    }
    old_ids = {case.task.id for case in build_holdout_cases()}
    assert not old_ids.intersection(case.task.id for case in first)
    assert all(case.case_id.startswith("test3-s1-A-") for case in first)


def test_holdout_a_r1_is_fresh_deterministic_and_exactly_ten_cases():
    first = build_holdout_a_r1()
    second = build_holdout_a_r1()
    assert [case.case_id for case in first] == [case.case_id for case in second]
    assert len(first) == 10
    assert all(case.case_id.startswith("test3-s1-AR1-") for case in first)
    assert {case.task.family for case in first} == {"state", "policy", "reconciliation"}
    assert {case.task.complexity for case in first} == {1, 2, 3, 4}

    prior_ids = {case.task.id for case in build_holdout_cases()}
    prior_ids.update(case.task.id for case in build_holdout_a())
    assert not prior_ids.intersection(case.task.id for case in first)


def test_s1_r1_seed_failure_is_verified_bad_and_does_not_mutate_task():
    for case in build_holdout_a_r1():
        before = asdict(case.task)
        candidate = build_seed_failure(case)
        result = evaluate_task(case.task, candidate.state, candidate.actions)
        assert result.success is False
        assert candidate.injected_faults
        assert candidate.metadata.get("s1_r1_seed_failure") is True
        assert asdict(case.task) == before
