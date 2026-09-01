from dataclasses import asdict

from inverted.oracle import evaluate_task
from inverted.test2_cases import build_execution_cases, build_formalization_cases, build_holdout_cases
from inverted.test3_s1_cases import (
    build_holdout_a,
    build_holdout_a_r1,
    build_holdout_a_r2,
    build_seed_failure,
    build_seed_failure_r2,
    r2_arm_order,
)


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


def test_holdout_a_r2_exact_preregistered_schedule_and_seed_namespace():
    cases = build_holdout_a_r2()
    assert len(cases) == 25
    expected_families = []
    for level in (1, 2, 3, 4):
        expected_families.extend([
            ("state", level),
            ("policy", level),
            ("reconciliation", level),
            ("preservation", level),
            ("dependency_order", level),
            ("repair_containment", level),
        ])
    expected_families.append(("repair_containment", 4))
    assert [(case.task.family, case.task.complexity) for case in cases] == expected_families
    assert [case.task.metadata["seed"] for case in cases] == [611000 + index * 229 for index in range(25)]
    assert all(case.case_id.startswith("test3-s1-AR2-") for case in cases)
    assert "stress" in cases[-1].case_id


def test_holdout_a_r2_seed_values_do_not_collide_with_prior_test_namespaces():
    prior_seeds = {case.task.metadata["seed"] for case in build_holdout_cases()}
    prior_seeds.update(case.task.metadata["seed"] for case in build_execution_cases())
    prior_seeds.update(case.task.metadata["seed"] for case in build_formalization_cases())
    prior_seeds.update(case.task.metadata["seed"] for case in build_holdout_a())
    prior_seeds.update(case.task.metadata["seed"] for case in build_holdout_a_r1())
    r2_seeds = {case.task.metadata["seed"] for case in build_holdout_a_r2()}
    assert not prior_seeds.intersection(r2_seeds)


def test_s1_r2_seed_failure_is_deterministic_verified_bad_and_task_immutable():
    for case in build_holdout_a_r2():
        before = asdict(case.task)
        first = build_seed_failure_r2(case)
        second = build_seed_failure_r2(case)
        assert asdict(first) == asdict(second)
        result = evaluate_task(case.task, first.state, first.actions)
        assert result.success is False
        assert first.metadata.get("s1_r2_seed_failure") is True
        assert asdict(case.task) == before


def test_r2_preservation_seed_fails_preserve_without_breaking_mutable_targets():
    for case in (row for row in build_holdout_a_r2() if row.task.family == "preservation"):
        result = evaluate_task(case.task, build_seed_failure_r2(case).state, build_seed_failure_r2(case).actions)
        failed_kinds = {req.kind for req in case.task.requirements if req.id in result.failed_requirement_ids}
        assert failed_kinds == {"preserve"}
        assert sum(req.kind == "preserve" and req.id in result.failed_requirement_ids for req in case.task.requirements) == 1


def test_r2_dependency_seed_keeps_actions_present_but_breaks_only_order():
    for case in (row for row in build_holdout_a_r2() if row.task.family == "dependency_order"):
        candidate = build_seed_failure_r2(case)
        result = evaluate_task(case.task, candidate.state, candidate.actions)
        failed_kinds = {req.kind for req in case.task.requirements if req.id in result.failed_requirement_ids}
        assert failed_kinds == {"action_before"}
        assert [action.op for action in candidate.actions].index("start") < [action.op for action in candidate.actions].index("grant")


def test_r2_containment_seed_is_localized_and_stress_case_has_two_faults():
    containment = [row for row in build_holdout_a_r2() if row.task.family == "repair_containment"]
    for case in containment:
        candidate = build_seed_failure_r2(case)
        result = evaluate_task(case.task, candidate.state, candidate.actions)
        failed = [req for req in case.task.requirements if req.id in result.failed_requirement_ids]
        expected = 2 if "stress" in case.case_id else 1
        assert len(failed) == expected
        assert all(req.kind == "equal" for req in failed)
        assert all(req.kind != "preserve" or req.id not in result.failed_requirement_ids for req in case.task.requirements)


def test_r2_arm_order_is_frozen_and_balanced():
    base = ("S1-A0", "S1-A1", "S1-A2", "S1-A3")
    for index in range(24):
        shift = index % 4
        assert r2_arm_order(index) == base[shift:] + base[:shift]
    assert r2_arm_order(24) == ("S1-A2", "S1-A0", "S1-A3", "S1-A1")
    for position in range(4):
        counts = {arm: 0 for arm in base}
        for index in range(24):
            counts[r2_arm_order(index)[position]] += 1
        assert set(counts.values()) == {6}
