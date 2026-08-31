from inverted.test2_cases import (
    build_audit_candidate_bank,
    build_execution_cases,
    build_formalization_cases,
    build_holdout_cases,
    build_repair_candidate_bank,
)


def test_formalization_cases_are_deterministic_and_cover_all_representation_classes():
    a = build_formalization_cases()
    b = build_formalization_cases()
    assert len(a) == 12
    assert [x.case_id for x in a] == [x.case_id for x in b]
    assert {x.representation for x in a} == {
        "structured", "natural", "paraphrased", "implicit", "perceptual_like"
    }
    assert {x.task.family for x in a} == {"state", "policy", "reconciliation"}


def test_execution_cases_are_exact_three_by_four_matrix():
    cases = build_execution_cases()
    assert len(cases) == 12
    assert {(x.task.family, x.task.complexity) for x in cases} == {
        (family, complexity)
        for family in ("state", "policy", "reconciliation")
        for complexity in (1, 2, 3, 4)
    }


def test_audit_bank_is_fixed_balanced_and_fault_diverse():
    bank = build_audit_candidate_bank()
    assert len(bank) == 20
    assert sum(x.oracle_success for x in bank) == 10
    assert sum(not x.oracle_success for x in bank) == 10
    assert len({x.case_id for x in bank}) == 20
    faults = {fault.split("+")[0] for x in bank for fault in x.candidate.injected_faults}
    assert {"omitted_requirement", "wrong_value", "unintended_side_effect"} <= faults
    assert {"ordering_violation", "forbidden_procedure"} & faults


def test_repair_bank_contains_only_oracle_failures_and_holdout_is_disjoint():
    repair = build_repair_candidate_bank()
    holdout = build_holdout_cases()
    assert len(repair) == 10
    assert all(not x.oracle_success for x in repair)
    assert len(holdout) == 12
    repair_tasks = {x.task.id for x in repair}
    holdout_tasks = {x.task.id for x in holdout}
    assert repair_tasks.isdisjoint(holdout_tasks)
