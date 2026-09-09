from __future__ import annotations

from inverted.capability_ratchet.causal_core import DivergenceClass
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.tomography_core import TomographyAxis, TomographyStatus
from inverted.capability_ratchet.tomography_eligibility import (
    TomographyEligibilityStatus,
    classify_tomography_eligibility,
    plan_eligible_tomography,
)

SHA = "a" * 64


def _classify(**changes):
    values = dict(
        failure_snapshot_id="failure-1",
        partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.TOOL_SELECTION,
        decision_ids=("D6",),
        reconstructable_state=True,
        answered_by_existing_evidence=False,
        requires_prior_localization=False,
        stage5_persistent_residual=False,
        stage6_external_boundary=False,
        historical_contrast=False,
    )
    values.update(changes)
    return classify_tomography_eligibility(**values)


def test_explicit_stage7_divergence_is_eligible_without_model_calls() -> None:
    result = _classify()
    assert result.status is TomographyEligibilityStatus.ELIGIBLE
    assert result.failure_snapshot_id == "failure-1"
    assert result.model_calls == 0
    assert "autopsy_stage7_divergence" in result.evidence_sources


def test_existing_canonical_answer_wins_over_new_probe() -> None:
    result = _classify(answered_by_existing_evidence=True)
    assert result.status is TomographyEligibilityStatus.ANSWERED_BY_EXISTING_EVIDENCE
    assert result.model_calls == 0


def test_missing_reconstructable_parent_state_is_not_eligible() -> None:
    result = _classify(reconstructable_state=False)
    assert result.status is TomographyEligibilityStatus.INSUFFICIENT_REPLAY_STATE


def test_fresh_and_sealed_are_protected_before_other_admission_logic() -> None:
    for partition in (Partition.FRESH, Partition.SEALED):
        result = _classify(
            partition=partition,
            answered_by_existing_evidence=True,
            reconstructable_state=False,
        )
        assert result.status is TomographyEligibilityStatus.PROTECTED_PARTITION
        assert result.model_calls == 0


def test_non_stage7_failure_requires_prior_localization_unless_external_boundary_exists() -> None:
    unresolved = _classify(
        divergence=DivergenceClass.UNKNOWN_NOVEL,
        decision_ids=("D2",),
    )
    assert unresolved.status is TomographyEligibilityStatus.REQUIRES_PRIOR_LOCALIZATION

    stage5 = _classify(
        divergence=DivergenceClass.UNKNOWN_NOVEL,
        decision_ids=("D2",),
        stage5_persistent_residual=True,
    )
    assert stage5.status is TomographyEligibilityStatus.ELIGIBLE
    assert "stage5_persistent_residual" in stage5.evidence_sources

    stage6 = _classify(
        divergence=DivergenceClass.UNKNOWN_NOVEL,
        decision_ids=("D2",),
        stage6_external_boundary=True,
    )
    assert stage6.status is TomographyEligibilityStatus.ELIGIBLE
    assert "stage6_external_boundary" in stage6.evidence_sources


def test_probe_must_be_capable_of_changing_a_stage7_decision() -> None:
    result = _classify(decision_ids=("D1", "D3", "D4"))
    assert result.status is TomographyEligibilityStatus.NO_DECISION_CHANGING_PROBE
    assert result.active_decision_ids == ()


def test_historical_reconstructable_contrast_can_enter_without_stage7_autopsy_label() -> None:
    result = _classify(
        partition=Partition.HISTORICAL,
        divergence=DivergenceClass.UNKNOWN_NOVEL,
        decision_ids=("D8",),
        historical_contrast=True,
    )
    assert result.status is TomographyEligibilityStatus.ELIGIBLE
    assert result.evidence_sources == ("historical_reconstructable_contrast",)


def test_explicit_prior_localization_gate_blocks_even_stage7_divergence() -> None:
    result = _classify(requires_prior_localization=True)
    assert result.status is TomographyEligibilityStatus.REQUIRES_PRIOR_LOCALIZATION


def test_auto_plan_is_zero_call_and_only_plans_eligible_cases() -> None:
    result = plan_eligible_tomography(
        failure_snapshot_id="failure-1",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.TOOL_SELECTION,
        decision_ids=("D6",),
        baseline_evidence_refs=("baseline-1",),
        intervention_ids={
            TomographyAxis.TOOL_AVAILABILITY: "int-available",
            TomographyAxis.TOOL_SELECTION: "int-selection",
        },
        changed_dimensions={
            TomographyAxis.TOOL_AVAILABILITY: ("request_envelopes.0.tools",),
            TomographyAxis.TOOL_SELECTION: ("request_envelopes.0.tools",),
        },
    )
    assert result.eligibility.status is TomographyEligibilityStatus.ELIGIBLE
    assert result.plan is not None
    assert result.plan.study.status is TomographyStatus.PLANNED
    assert result.model_calls == 0
    assert result.plan.model_calls == 0

    protected = plan_eligible_tomography(
        failure_snapshot_id="failure-2",
        parent_state_hash=SHA,
        partition=Partition.FRESH,
        divergence=DivergenceClass.TOOL_SELECTION,
        decision_ids=("D6",),
        baseline_evidence_refs=("baseline-2",),
        intervention_ids={},
        changed_dimensions={},
    )
    assert protected.eligibility.status is TomographyEligibilityStatus.PROTECTED_PARTITION
    assert protected.plan is None
    assert protected.model_calls == 0
