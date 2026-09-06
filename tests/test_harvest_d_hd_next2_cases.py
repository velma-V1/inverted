import pytest

from inverted.harvest_d.hd_next2.cases import (
    OPERATING_REGIONS,
    describe_hd_next2_case,
    generate_cross_region_cases,
    generate_hd_next2_cases,
)


def test_development_generation_covers_exactly_the_eight_operating_regions():
    cases = generate_hd_next2_cases("development", 20260921, 4)

    assert len(cases) == 32
    assert {case.metadata["hd_next2_region"] for case in cases} == set(OPERATING_REGIONS)
    assert all(case.metadata["partition"] == "development" for case in cases)


def test_generation_is_deterministic_and_partitions_are_disjoint():
    first = generate_hd_next2_cases("development", 20260921, 2)
    second = generate_hd_next2_cases("development", 20260921, 2)
    sealed = generate_hd_next2_cases("sealed", 20261021, 2)

    assert [(case.case_id, case.oracle.expected, case.metadata) for case in first] == [
        (case.case_id, case.oracle.expected, case.metadata) for case in second
    ]
    assert {case.case_id for case in first}.isdisjoint({case.case_id for case in sealed})


def test_policy_ordering_cases_expose_only_system_authored_answer_vocabulary():
    cases = generate_hd_next2_cases("development", 20260921, 4)
    policy = [case for case in cases if case.metadata["hd_next2_region"] == "POLICY_ORDERING"]

    assert policy
    for case in policy:
        assert {"VERIFY_BEFORE_COMMIT", "COMMIT_BEFORE_VERIFY"} <= set(case.metadata["answer_vocabulary"])
        assert case.oracle.expected["answer"] in case.metadata["answer_vocabulary"]
        assert "expected" not in str(case.metadata).lower()
        assert "oracle" not in str(case.metadata).lower()


def test_compound_templates_have_exactly_two_distinct_region_labels():
    cases = generate_cross_region_cases("development", 20260921)

    assert len(cases) == 4
    assert [case.metadata["compound_template"] for case in cases] == [
        "authority+transaction",
        "evidence+global-interaction",
        "state+dependency-recovery",
        "policy-ordering+verifier-oracle",
    ]
    assert all(len(case.metadata["hd_next2_regions"]) == 2 for case in cases)
    assert all(len(set(case.metadata["hd_next2_regions"])) == 2 for case in cases)


def test_description_is_stable_and_does_not_reveal_oracle():
    case = generate_hd_next2_cases("development", 20260921, 1)[0]
    description = describe_hd_next2_case(case)

    assert description["region"] in OPERATING_REGIONS
    assert description["family"] == case.family
    assert "expected" not in str(description).lower()
    assert "oracle" not in str(description).lower()


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        generate_hd_next2_cases("unknown", 1, 1)
    with pytest.raises(ValueError):
        generate_hd_next2_cases("development", 1, 0)
