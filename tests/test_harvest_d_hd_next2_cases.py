from copy import deepcopy

import pytest

from inverted.harvest_d.hd_next2.cases import (
    OPERATING_REGIONS,
    _compound_spec,
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
    other_development = generate_hd_next2_cases("development", 20261021, 2)

    assert [(case.case_id, case.oracle.expected, case.metadata) for case in first] == [
        (case.case_id, case.oracle.expected, case.metadata) for case in second
    ]
    assert {case.case_id for case in first}.isdisjoint({case.case_id for case in other_development})


def test_policy_ordering_is_derived_from_visible_facts_without_answer_leakage():
    cases = generate_hd_next2_cases("development", 20260921, 4)
    policy = [case for case in cases if case.metadata["hd_next2_region"] == "POLICY_ORDERING"]

    assert policy
    answers = set()
    for case in policy:
        assert {"VERIFY_BEFORE_COMMIT", "COMMIT_BEFORE_VERIFY"} <= set(case.metadata["answer_vocabulary"])
        answers.add(case.oracle.expected["answer"])
        facts = case.metadata["policy_scenario"]
        semantic_context = {
            "prompt": case.prompt,
            "metadata": {key: value for key, value in case.metadata.items() if key != "answer_vocabulary"},
        }
        assert case.oracle.expected["answer"] not in str(semantic_context)
        if facts["irreversible_final_effect"]:
            assert facts["precommit_verification_available"]
            assert facts["verification_required"]
            inferred = "VERIFY_BEFORE_COMMIT"
        else:
            assert facts["reversible_staged_operation"]
            assert facts["artifact_creation_required"]
            assert facts["rollback_available"]
            inferred = "COMMIT_BEFORE_VERIFY"
        assert inferred == case.oracle.expected["answer"]
    assert answers == {"VERIFY_BEFORE_COMMIT", "COMMIT_BEFORE_VERIFY"}


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


def test_compounds_are_complete_only_with_both_region_mechanisms():
    cases = generate_cross_region_cases("development", 20260921)

    for case in cases:
        regions = tuple(case.metadata["hd_next2_regions"])
        context = case.metadata["compound_context"]
        assert set(context) == set(regions)
        assert all(context[region] for region in regions)
        assert all(context[region]["required"] for region in regions)
        assert all(context[region]["facts"] for region in regions)
        for removed in regions:
            remaining = {region: context[region] for region in regions if region != removed}
            assert set(remaining) != set(regions)


def test_compound_vocabularies_are_joint_cross_products_and_oracles_use_both_components():
    cases = generate_cross_region_cases("development", 20260921)

    expected_vocabularies = {
        "authority+transaction": {
            "AUTHORITY_RESTRICT__TRANSACTION_RECONCILE",
            "AUTHORITY_RESTRICT__TRANSACTION_START",
            "AUTHORITY_PROCEED__TRANSACTION_RECONCILE",
            "AUTHORITY_PROCEED__TRANSACTION_START",
        },
        "evidence+global-interaction": {
            "EVIDENCE_REQUEST__GLOBAL_REJECT_LOCAL",
            "EVIDENCE_REQUEST__GLOBAL_ACCEPT_LOCAL",
            "EVIDENCE_SUFFICIENT__GLOBAL_REJECT_LOCAL",
            "EVIDENCE_SUFFICIENT__GLOBAL_ACCEPT_LOCAL",
        },
        "state+dependency-recovery": {
            "STATE_USE_CURRENT__DEPENDENCY_PARENT_FIRST",
            "STATE_USE_CURRENT__DEPENDENCY_CHILD_READY",
            "STATE_USE_STALE__DEPENDENCY_PARENT_FIRST",
            "STATE_USE_STALE__DEPENDENCY_CHILD_READY",
        },
        "policy-ordering+verifier-oracle": {
            "ORDER_VERIFY_FIRST__VERIFIER_TRUST",
            "ORDER_VERIFY_FIRST__MODEL_TRUST",
            "ORDER_COMMIT_STAGED__VERIFIER_TRUST",
            "ORDER_COMMIT_STAGED__MODEL_TRUST",
        },
    }
    for case in cases:
        expected = case.oracle.expected
        context = case.metadata["compound_context"]
        assert expected["answer"] in case.metadata["answer_vocabulary"]
        assert set(case.metadata["answer_vocabulary"]) == expected_vocabularies[case.metadata["compound_template"]]
        assert len(expected["answer"].split("__")) == 2
        assert expected["disposition"] == case.expected_disposition.value
        assert all(facts["required"] for facts in context.values())


@pytest.mark.parametrize(
    ("template", "left_mutation", "left_answer", "right_mutation", "right_answer"),
    [
        (
            "authority+transaction",
            lambda context: context["AUTHORITY_SCOPE"]["facts"]["I10"].update(scope_match=True),
            "AUTHORITY_PROCEED__TRANSACTION_RECONCILE",
            lambda context: context["TRANSACTION"]["facts"]["I4"].update(external_effect_status="KNOWN"),
            "AUTHORITY_RESTRICT__TRANSACTION_START",
        ),
        (
            "evidence+global-interaction",
            lambda context: context["EVIDENCE_TRUST"]["facts"]["I4"].update(missing=[]),
            "EVIDENCE_SUFFICIENT__GLOBAL_REJECT_LOCAL",
            lambda context: context["GLOBAL_INTERACTION"]["facts"]["I2"].update(global_state_valid=True),
            "EVIDENCE_REQUEST__GLOBAL_ACCEPT_LOCAL",
        ),
        (
            "state+dependency-recovery",
            lambda context: context["STATE_PRESERVATION"]["facts"]["I6"].update(must_use_current_version=False),
            "STATE_USE_STALE__DEPENDENCY_PARENT_FIRST",
            lambda context: context["STRUCTURAL_DEPENDENCY_RECOVERY"]["facts"]["I6"].update(child_requires_parent=False),
            "STATE_USE_CURRENT__DEPENDENCY_CHILD_READY",
        ),
        (
            "policy-ordering+verifier-oracle",
            lambda context: context["POLICY_ORDERING"]["facts"].update(
                irreversible_final_effect=False,
                precommit_verification_available=False,
                verification_required=False,
                reversible_staged_operation=True,
                artifact_creation_required=True,
                rollback_available=True,
            ),
            "ORDER_COMMIT_STAGED__VERIFIER_TRUST",
            lambda context: context["VERIFIER_ORACLE"]["facts"]["I6"].update(model_may_not_self_certify=False),
            "ORDER_VERIFY_FIRST__MODEL_TRUST",
        ),
    ],
)
def test_each_compound_component_changes_when_its_decisive_visible_facts_change(
    template, left_mutation, left_answer, right_mutation, right_answer
):
    case = next(case for case in generate_cross_region_cases("development", 20260921) if case.metadata["compound_template"] == template)
    original = case.oracle.expected["answer"]

    left_context = deepcopy(case.metadata["compound_context"])
    left_mutation(left_context)
    assert _compound_spec(template, left_context)[1] == left_answer
    assert _compound_spec(template, left_context)[1] != original

    right_context = deepcopy(case.metadata["compound_context"])
    right_mutation(right_context)
    assert _compound_spec(template, right_context)[1] == right_answer
    assert _compound_spec(template, right_context)[1] != original


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
