from inverted.test2_cases import build_holdout_cases
from inverted.test3_s1_cases import build_holdout_a


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
