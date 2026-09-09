from __future__ import annotations

from inverted.capability_ratchet.causal_core import DivergenceClass
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.tomography_analysis import TomographyAnalyzer
from inverted.capability_ratchet.tomography_core import (
    TomographyAxis,
    TomographyDisposition,
    TomographyOutcome,
    TomographyProbeSpec,
    TomographyStatus,
    TomographyStudy,
)
from inverted.capability_ratchet.tomography_planner import TomographyPlanner

SHA = "a" * 64


def _study(*, probe_ids=("probe-1",), projected_calls=1, decisions=("D6",)) -> TomographyStudy:
    return TomographyStudy(
        study_id="study-1",
        failure_snapshot_id="failure-1",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        decision_ids=decisions,
        candidate_axes=(TomographyAxis.TOOL_AVAILABILITY,),
        baseline_evidence_refs=("baseline-1",),
        probe_ids=tuple(probe_ids),
        max_new_probes=3,
        projected_calls=projected_calls,
        status=TomographyStatus.PLANNED,
    )


def _probe(axis: TomographyAxis, *, probe_id="probe-1") -> TomographyProbeSpec:
    return TomographyProbeSpec(
        probe_id=probe_id,
        study_id="study-1",
        axis=axis,
        intervention_id=f"int-{probe_id}",
        control_intervention_id=None,
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        expected_implication=f"isolate {axis.value}",
        projected_calls=1,
        protected=False,
    )


def _outcome(axis: TomographyAxis, *, probe_id="probe-1", success=True) -> TomographyOutcome:
    return TomographyOutcome(
        outcome_id=f"out-{probe_id}",
        study_id="study-1",
        probe_id=probe_id,
        replay_result_id=f"result-{probe_id}",
        semantic_success=success,
        contract_valid=success,
        score=1.0 if success else 0.0,
        first_divergence=None if success else "SEMANTIC_FAIL",
        comparison_refs=("baseline-1",),
        protected_regression=False,
        child_failure_snapshot_id=None if success else f"child-{probe_id}",
    )


def test_tool_planner_cannot_skip_execution_result_before_interpretation() -> None:
    plan = TomographyPlanner().plan(
        failure_snapshot_id="failure-1",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.TOOL_INTERPRETATION,
        decision_ids=("D6",),
        baseline_evidence_refs=("baseline-1",),
        intervention_ids={
            TomographyAxis.TOOL_SELECTION: "int-select",
            TomographyAxis.TOOL_ARGUMENTS: "int-args",
            TomographyAxis.TOOL_EXECUTION_RESULT: "int-exec",
            TomographyAxis.TOOL_RESULT_INTERPRETATION: "int-interpret",
        },
        changed_dimensions={
            TomographyAxis.TOOL_SELECTION: ("request_envelopes.0.tools",),
            TomographyAxis.TOOL_ARGUMENTS: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.TOOL_EXECUTION_RESULT: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.TOOL_RESULT_INTERPRETATION: ("request_envelopes.0.messages.0.content",),
        },
        resolved_axes=(TomographyAxis.TOOL_AVAILABILITY,),
    )
    assert [item.axis for item in plan.probes] == [
        TomographyAxis.TOOL_SELECTION,
        TomographyAxis.TOOL_ARGUMENTS,
        TomographyAxis.TOOL_EXECUTION_RESULT,
    ]

    follow_up = TomographyPlanner().plan(
        failure_snapshot_id="failure-1",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.TOOL_INTERPRETATION,
        decision_ids=("D6",),
        baseline_evidence_refs=("baseline-1",),
        intervention_ids={
            TomographyAxis.TOOL_EXECUTION_RESULT: "int-exec",
            TomographyAxis.TOOL_RESULT_INTERPRETATION: "int-interpret",
        },
        changed_dimensions={
            TomographyAxis.TOOL_EXECUTION_RESULT: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.TOOL_RESULT_INTERPRETATION: ("request_envelopes.0.messages.0.content",),
        },
        resolved_axes=(
            TomographyAxis.TOOL_AVAILABILITY,
            TomographyAxis.TOOL_SELECTION,
            TomographyAxis.TOOL_ARGUMENTS,
        ),
    )
    assert [item.axis for item in follow_up.probes] == [
        TomographyAxis.TOOL_EXECUTION_RESULT,
        TomographyAxis.TOOL_RESULT_INTERPRETATION,
    ]


def test_verifier_planner_isolates_visibility_before_feedback() -> None:
    plan = TomographyPlanner().plan(
        failure_snapshot_id="failure-1",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.VERIFIER_FEEDBACK,
        decision_ids=("D8",),
        baseline_evidence_refs=("baseline-1",),
        intervention_ids={
            TomographyAxis.VERIFIER_VISIBILITY: "int-visible",
            TomographyAxis.VERIFIER_FEEDBACK: "int-feedback",
        },
        changed_dimensions={
            TomographyAxis.VERIFIER_VISIBILITY: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.VERIFIER_FEEDBACK: ("request_envelopes.0.messages.0.content",),
        },
    )
    assert [item.axis for item in plan.probes] == [
        TomographyAxis.VERIFIER_VISIBILITY,
        TomographyAxis.VERIFIER_FEEDBACK,
    ]


def test_skill_planner_uses_only_corrected_trigger_and_procedure_axes() -> None:
    plan = TomographyPlanner().plan(
        failure_snapshot_id="failure-1",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.SKILL_DEFICIT,
        decision_ids=("D7",),
        baseline_evidence_refs=("baseline-1",),
        intervention_ids={
            TomographyAxis.SKILL_TRIGGER: "int-trigger",
            TomographyAxis.SKILL_PROCEDURE: "int-procedure",
        },
        changed_dimensions={
            TomographyAxis.SKILL_TRIGGER: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.SKILL_PROCEDURE: ("request_envelopes.0.messages.0.content",),
        },
    )
    assert [item.axis for item in plan.probes] == [
        TomographyAxis.SKILL_TRIGGER,
        TomographyAxis.SKILL_PROCEDURE,
    ]


def test_tool_execution_result_repair_is_execution_failure_not_model_failure() -> None:
    profile = TomographyAnalyzer().analyze(
        _study(),
        (_probe(TomographyAxis.TOOL_EXECUTION_RESULT),),
        (_outcome(TomographyAxis.TOOL_EXECUTION_RESULT),),
    )
    assert profile.dispositions == (TomographyDisposition.TOOL_EXECUTION_FAILURE,)
    assert profile.model_internal_boundary is False
    assert profile.promotion_allowed is False
    assert profile.route_back_stage is None


def test_disposition_does_not_become_movement_without_existing_causal_promotion() -> None:
    verifier = _probe(TomographyAxis.VERIFIER_FEEDBACK, probe_id="verify")
    verifier_outcome = _outcome(TomographyAxis.VERIFIER_FEEDBACK, probe_id="verify")
    study = _study(probe_ids=("verify",), projected_calls=1, decisions=("D8",))

    ownership_only = TomographyAnalyzer().analyze(study, (verifier,), (verifier_outcome,))
    assert ownership_only.dispositions == (TomographyDisposition.VERIFIER_SUFFICIENT,)
    assert ownership_only.promotion_allowed is False
    assert ownership_only.route_back_stage is None

    movement = TomographyAnalyzer().analyze(
        study,
        (verifier,),
        (verifier_outcome,),
        causal_movement_earned=True,
    )
    assert movement.dispositions == (TomographyDisposition.VERIFIER_SUFFICIENT,)
    assert movement.promotion_allowed is True
    assert movement.route_back_stage == "stage4"


def test_recovery_and_skill_are_candidates_not_automatic_promotion() -> None:
    recovery = _probe(TomographyAxis.TARGETED_RECOVERY, probe_id="recovery")
    generic = _probe(TomographyAxis.GENERIC_RETRY_CONTROL, probe_id="generic")
    recovery_study = _study(probe_ids=("recovery", "generic"), projected_calls=2, decisions=("D8",))
    recovery_profile = TomographyAnalyzer().analyze(
        recovery_study,
        (recovery, generic),
        (
            _outcome(TomographyAxis.TARGETED_RECOVERY, probe_id="recovery", success=True),
            _outcome(TomographyAxis.GENERIC_RETRY_CONTROL, probe_id="generic", success=False),
        ),
    )
    assert recovery_profile.dispositions == (TomographyDisposition.RECOVERY_SUFFICIENT,)
    assert recovery_profile.promotion_allowed is False

    skill = _probe(TomographyAxis.SKILL_PROCEDURE, probe_id="skill")
    skill_study = _study(probe_ids=("skill",), projected_calls=1, decisions=("D7",))
    skill_profile = TomographyAnalyzer().analyze(
        skill_study,
        (skill,),
        (_outcome(TomographyAxis.SKILL_PROCEDURE, probe_id="skill"),),
        skill_related_success_count=2,
    )
    assert skill_profile.dispositions == (TomographyDisposition.SKILL_CANDIDATE,)
    assert skill_profile.promotion_allowed is False


def test_escalation_safe_stop_and_model_residual_are_distinct_boundaries() -> None:
    escalation = _probe(TomographyAxis.ESCALATION_REFERENCE, probe_id="escalate")
    study = _study(probe_ids=("escalate",), projected_calls=1, decisions=("D10", "D11"))

    escalation_profile = TomographyAnalyzer().analyze(
        study,
        (escalation,),
        (_outcome(TomographyAxis.ESCALATION_REFERENCE, probe_id="escalate", success=True),),
        external_supports_exhausted=True,
    )
    assert escalation_profile.dispositions == (TomographyDisposition.ESCALATION_CANDIDATE,)
    assert escalation_profile.promotion_allowed is False
    assert escalation_profile.model_internal_boundary is False

    safe_stop_profile = TomographyAnalyzer().analyze(
        study,
        (escalation,),
        (_outcome(TomographyAxis.ESCALATION_REFERENCE, probe_id="escalate", success=False),),
        external_supports_exhausted=True,
        safe_stop_required=True,
    )
    assert safe_stop_profile.dispositions == (TomographyDisposition.SAFE_STOP_BOUNDARY,)
    assert safe_stop_profile.model_internal_boundary is False
    assert safe_stop_profile.promotion_allowed is False

    model_profile = TomographyAnalyzer().analyze(
        study,
        (escalation,),
        (_outcome(TomographyAxis.ESCALATION_REFERENCE, probe_id="escalate", success=False),),
        external_supports_exhausted=True,
    )
    assert model_profile.dispositions == (TomographyDisposition.MODEL_INTERNAL_RESIDUAL,)
    assert model_profile.model_internal_boundary is True
    assert model_profile.promotion_allowed is False
