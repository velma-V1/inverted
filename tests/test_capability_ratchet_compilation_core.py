from __future__ import annotations

import math

import pytest

from inverted.capability_ratchet.compilation_core import (
    COMPILATION_KIND_ORDER,
    CompilationCandidate,
    CompilationDisposition,
    CompilationEligibilityStatus,
    CompilationKind,
    CompilationPlan,
    CompilationPolicy,
    CompiledCapability,
)
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.mutation_core import GeneralizationClass


EXPECTED_ORDER = (
    CompilationKind.DETERMINISTIC_RULE,
    CompilationKind.STATE_REPRESENTATION,
    CompilationKind.FORMATTER_PARSER_VALIDATOR,
    CompilationKind.TOOL_POLICY,
    CompilationKind.SKILL_POLICY,
    CompilationKind.REASONING_POLICY,
    CompilationKind.VERIFIER_RECOVERY_POLICY,
    CompilationKind.FINE_TUNE_CANDIDATE,
    CompilationKind.ESCALATION_POLICY,
    CompilationKind.SAFE_STOP_BOUNDARY,
)


def _candidate(**overrides) -> CompilationCandidate:
    values = dict(
        failure_snapshot_id="failure-1",
        mechanism_id="mechanism-1",
        generalization_profile_id="profile-1",
        prior_generalized_evidence_ref=None,
        generalization_class=GeneralizationClass.REGION_MECHANISM,
        mechanism_label_ids=("label-1",),
        evidence_refs=("result-1", "profile-1"),
        source_hashes={"profile-1": "a" * 64},
        supported_kinds=(CompilationKind.TOOL_POLICY,),
        excluded_cheaper_kinds={
            CompilationKind.DETERMINISTIC_RULE.value: "tool capability cannot be replaced by local computation",
            CompilationKind.STATE_REPRESENTATION.value: "state is already complete",
            CompilationKind.FORMATTER_PARSER_VALIDATOR.value: "failure is not contract/interface owned",
        },
        trigger_contract={"tool_eligible": True, "failure_class": "TOOL_SELECTION"},
        compiled_payload={"allowed_tool": "calculator", "selection_rule": "when arithmetic is required"},
        verifier_contract={"postcondition": "numeric result parses"},
        negative_transfer_boundary=("do not route direct-solved non-tool cases",),
        tested_region="arithmetic tool-eligible failures in mutation regions r1-r3",
        rollback_action="DISABLE",
        partition=Partition.HISTORICAL,
        operating_surface_profile_id=None,
        tomography_assessment_id="assessment-1",
        model_internal_residual=False,
    )
    values.update(overrides)
    return CompilationCandidate.create(**values)


def test_owner_order_is_exact_governing_v3_order() -> None:
    assert COMPILATION_KIND_ORDER == EXPECTED_ORDER
    assert CompilationPolicy().owner_order == EXPECTED_ORDER


def test_stage8_dispositions_are_separate_from_promotion_vocabulary() -> None:
    values = {item.value for item in CompilationDisposition}
    assert values.isdisjoint({"MOVEMENT", "TIER_CANDIDATE", "CERTIFIED"})
    assert CompilationEligibilityStatus.ELIGIBLE.value == "ELIGIBLE"


def test_candidate_is_content_addressed_and_immutable() -> None:
    left = _candidate()
    right = _candidate()
    assert left.candidate_id == right.candidate_id
    with pytest.raises(TypeError):
        left.trigger_contract["x"] = 1  # type: ignore[index]


def test_candidate_rejects_instance_patch_and_protected_partition() -> None:
    with pytest.raises(ValueError, match="INSTANCE_PATCH"):
        _candidate(generalization_class=GeneralizationClass.INSTANCE_PATCH)
    with pytest.raises(ValueError, match="FRESH|SEALED|protected"):
        _candidate(partition=Partition.FRESH)


def test_candidate_rejects_hidden_oracle_trigger_keys() -> None:
    with pytest.raises(ValueError, match="oracle|family"):
        _candidate(trigger_contract={"oracle_answer": "42"})
    with pytest.raises(ValueError, match="oracle|family"):
        _candidate(trigger_contract={"nested": {"family_label": "arithmetic"}})


def test_candidate_requires_trigger_boundary_tested_region_and_rollback() -> None:
    with pytest.raises(ValueError, match="trigger"):
        _candidate(trigger_contract={})
    with pytest.raises(ValueError, match="negative_transfer"):
        _candidate(negative_transfer_boundary=())
    with pytest.raises(ValueError, match="tested_region"):
        _candidate(tested_region="")
    with pytest.raises(ValueError, match="rollback"):
        _candidate(rollback_action="")


def test_candidate_rejects_nonfinite_payload_numbers() -> None:
    with pytest.raises(TypeError, match="finite"):
        _candidate(compiled_payload={"threshold": math.inf})


def test_candidate_requires_one_generalization_source() -> None:
    with pytest.raises(ValueError, match="generalization"):
        _candidate(generalization_profile_id=None, prior_generalized_evidence_ref=None)
    with pytest.raises(ValueError, match="generalization"):
        _candidate(prior_generalized_evidence_ref="prior-1")


def test_plan_is_zero_call_and_content_addressed() -> None:
    candidate = _candidate()
    plan = CompilationPlan.create(
        candidate_id=candidate.candidate_id,
        selected_kind=CompilationKind.TOOL_POLICY,
        rejected_cheaper_kinds=candidate.excluded_cheaper_kinds,
        evidence_refs=candidate.evidence_refs,
        expected_disposition=CompilationDisposition.COMPILED,
    )
    assert plan.projected_model_calls == 0
    assert plan == CompilationPlan.create(
        candidate_id=candidate.candidate_id,
        selected_kind=CompilationKind.TOOL_POLICY,
        rejected_cheaper_kinds=candidate.excluded_cheaper_kinds,
        evidence_refs=candidate.evidence_refs,
        expected_disposition=CompilationDisposition.COMPILED,
    )
    with pytest.raises(ValueError, match="zero"):
        CompilationPlan(
            plan_id=plan.plan_id,
            candidate_id=plan.candidate_id,
            selected_kind=plan.selected_kind,
            rejected_cheaper_kinds=plan.rejected_cheaper_kinds,
            evidence_refs=plan.evidence_refs,
            projected_model_calls=1,
            expected_disposition=plan.expected_disposition,
        )


def test_compiled_capability_version_one_is_rollback_safe_and_not_deployable() -> None:
    candidate = _candidate()
    capability = CompiledCapability.create(
        candidate=candidate,
        selected_kind=CompilationKind.TOOL_POLICY,
        version=1,
        previous_capability_id=None,
        disposition=CompilationDisposition.COMPILED,
        handoff="STAGE10_OR_STAGE11",
    )
    assert capability.capability_key
    assert capability.capability_id
    assert capability.version == 1
    assert capability.previous_capability_id is None
    assert capability.rollback_action == "DISABLE"
    assert capability.deployment_allowed is False
    assert capability.fresh_validation_required is True


def test_compiled_capability_version_two_requires_previous_version() -> None:
    candidate = _candidate()
    v1 = CompiledCapability.create(
        candidate=candidate,
        selected_kind=CompilationKind.TOOL_POLICY,
        version=1,
        previous_capability_id=None,
        disposition=CompilationDisposition.COMPILED,
        handoff="STAGE10_OR_STAGE11",
    )
    with pytest.raises(ValueError, match="previous"):
        CompiledCapability.create(
            candidate=candidate,
            selected_kind=CompilationKind.TOOL_POLICY,
            version=2,
            previous_capability_id=None,
            disposition=CompilationDisposition.COMPILED,
            handoff="STAGE10_OR_STAGE11",
        )
    v2 = CompiledCapability.create(
        candidate=candidate,
        selected_kind=CompilationKind.TOOL_POLICY,
        version=2,
        previous_capability_id=v1.capability_id,
        disposition=CompilationDisposition.COMPILED,
        handoff="STAGE10_OR_STAGE11",
    )
    assert v2.capability_key == v1.capability_key
    assert v2.capability_id != v1.capability_id
    assert v2.previous_capability_id == v1.capability_id
