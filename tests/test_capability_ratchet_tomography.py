from __future__ import annotations

import json

import pytest

from inverted.capability_ratchet.causal_core import DivergenceClass, InterventionDefinition, InterventionKind
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.tomography_analysis import TomographyAnalyzer
from inverted.capability_ratchet.tomography_core import (
    TomographyAxis,
    TomographyDisposition,
    TomographyOutcome,
    TomographyProbe,
    TomographyProfile,
    TomographyStatus,
    TomographyStopReason,
    TomographyStudy,
)
from inverted.capability_ratchet.tomography_planner import TomographyPlanner
from inverted.capability_ratchet.tomography_replay import TomographyReplayCompiler
from inverted.capability_ratchet.tomography_store import TomographyEvidenceStore

SHA = "a" * 64


def study(**changes):
    values = dict(study_id="study-1", failure_snapshot_id="failure-1", parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT, decision_ids=("D6",),
        candidate_axes=(TomographyAxis.TOOL_AVAILABILITY,), baseline_evidence_refs=("replay-result-baseline",),
        probe_ids=("probe-1",), max_new_probes=3, projected_calls=1,
        status=TomographyStatus.PLANNED, stop_reason=None)
    values.update(changes)
    return TomographyStudy(**values)


def probe(axis=TomographyAxis.TOOL_AVAILABILITY, **changes):
    values = dict(probe_id="probe-1", study_id="study-1", axis=axis, intervention_id="int-1",
        control_intervention_id=None, changed_dimensions=("request_envelopes.0.tools",),
        expected_implication="diagnostic contrast", projected_calls=1, protected=False)
    values.update(changes)
    return TomographyProbe(**values)


def outcome(axis=TomographyAxis.TOOL_AVAILABILITY, success=True, **changes):
    values = dict(outcome_id=f"out-{axis.value.lower()}", study_id="study-1", probe_id="probe-1",
        replay_result_id=f"replay-{axis.value.lower()}", semantic_success=success, contract_valid=success,
        score=1.0 if success else 0.0, first_divergence=None if success else "SEMANTIC_FAIL",
        comparison_refs=("replay-result-baseline",), protected_regression=False,
        child_failure_snapshot_id=None if success else "child-1")
    values.update(changes)
    return TomographyOutcome(**values)


def test_stage7_contract_has_exact_axes_and_never_certifies():
    assert [x.value for x in TomographyAxis] == [
        "TOOL_AVAILABILITY", "TOOL_SELECTION", "TOOL_ARGUMENTS", "TOOL_EXECUTION_RESULT",
        "TOOL_RESULT_INTERPRETATION", "VERIFIER_VISIBILITY", "VERIFIER_FEEDBACK", "TARGETED_RECOVERY",
        "GENERIC_RETRY_CONTROL", "SKILL_PROCEDURE", "SKILL_TRIGGER", "ESCALATION_REFERENCE",
    ]
    with pytest.raises(ValueError, match="cannot certify"):
        TomographyProfile(profile_id="profile-1", study_id="study-1",
            dispositions=(TomographyDisposition.TOOL_REQUIRED,), supported_hypotheses=("hyp-1",),
            falsified_hypotheses=(), evidence_refs=("replay-1",), next_decisions=("D6",),
            route_back_stage="stage4", model_internal_boundary=False, promotion_allowed=True,
            certification_allowed=True)


def test_stopped_study_requires_stop_reason_and_planned_study_forbids_one():
    with pytest.raises(ValueError):
        study(status=TomographyStatus.STOPPED, stop_reason=None, probe_ids=(), projected_calls=0)
    with pytest.raises(ValueError):
        study(stop_reason=TomographyStopReason.NO_ELIGIBLE_RESIDUALS)


def test_planner_tool_ladder_is_ordered_bounded_and_existing_evidence_first():
    planner = TomographyPlanner()
    plan = planner.plan(failure_snapshot_id="failure-1", parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT, divergence=DivergenceClass.TOOL_INTERPRETATION,
        decision_ids=("D6",), baseline_evidence_refs=("baseline",),
        intervention_ids={TomographyAxis.TOOL_SELECTION: "int-select", TomographyAxis.TOOL_ARGUMENTS: "int-args",
            TomographyAxis.TOOL_EXECUTION_RESULT: "int-exec", TomographyAxis.TOOL_RESULT_INTERPRETATION: "int-interpret"},
        changed_dimensions={TomographyAxis.TOOL_SELECTION: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.TOOL_ARGUMENTS: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.TOOL_EXECUTION_RESULT: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.TOOL_RESULT_INTERPRETATION: ("request_envelopes.0.messages.0.content",)},
        resolved_axes=(TomographyAxis.TOOL_AVAILABILITY,))
    assert [p.axis for p in plan.probes] == [TomographyAxis.TOOL_SELECTION, TomographyAxis.TOOL_ARGUMENTS,
        TomographyAxis.TOOL_EXECUTION_RESULT]
    assert plan.study.projected_calls == 3 and plan.study.max_new_probes == 3


def test_planner_never_schedules_standalone_generic_retry_or_blind_third_retry():
    plan = TomographyPlanner().plan(failure_snapshot_id="failure-1", parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT, divergence=DivergenceClass.RECOVERY_POLICY,
        decision_ids=("D8",), baseline_evidence_refs=("baseline",),
        intervention_ids={TomographyAxis.TARGETED_RECOVERY: "int-target", TomographyAxis.GENERIC_RETRY_CONTROL: "int-control"},
        changed_dimensions={TomographyAxis.TARGETED_RECOVERY: ("request_envelopes.0.messages.0.content",),
            TomographyAxis.GENERIC_RETRY_CONTROL: ("request_envelopes.0.messages.0.content",)})
    assert [p.axis for p in plan.probes] == [TomographyAxis.TARGETED_RECOVERY, TomographyAxis.GENERIC_RETRY_CONTROL]
    assert len(plan.probes) == 2


def test_unknown_novel_stops_without_inventing_stage7_cause():
    plan = TomographyPlanner().plan(failure_snapshot_id="failure-1", parent_state_hash=SHA,
        partition=Partition.HISTORICAL, divergence=DivergenceClass.UNKNOWN_NOVEL,
        decision_ids=("D1",), baseline_evidence_refs=("baseline",), intervention_ids={}, changed_dimensions={})
    assert plan.study.status is TomographyStatus.STOPPED
    assert plan.study.stop_reason is TomographyStopReason.NO_ELIGIBLE_RESIDUALS
    assert plan.probes == () and plan.model_calls == 0


def test_model_internal_boundary_requires_external_support_exhaustion():
    planner = TomographyPlanner()
    kwargs = dict(failure_snapshot_id="failure-1", parent_state_hash=SHA, partition=Partition.DEVELOPMENT,
        divergence=DivergenceClass.MODEL_CAPABILITY_LIMIT, decision_ids=("D10", "D11"),
        baseline_evidence_refs=("baseline",), intervention_ids={}, changed_dimensions={})
    assert planner.plan(**kwargs, external_supports_exhausted=False).study.stop_reason is TomographyStopReason.INSUFFICIENT_OBSERVABLE_EVIDENCE
    assert planner.plan(**kwargs, external_supports_exhausted=True).study.stop_reason is TomographyStopReason.MODEL_INTERNAL_BOUNDARY


@pytest.mark.parametrize("axis,expected", [
    (TomographyAxis.TOOL_AVAILABILITY, TomographyDisposition.TOOL_REQUIRED),
    (TomographyAxis.TOOL_SELECTION, TomographyDisposition.TOOL_SELECTION_DEFICIT),
    (TomographyAxis.TOOL_ARGUMENTS, TomographyDisposition.TOOL_ARGUMENT_DEFICIT),
    (TomographyAxis.TOOL_RESULT_INTERPRETATION, TomographyDisposition.TOOL_INTERPRETATION_DEFICIT),
])
def test_tool_tomography_dispositions(axis, expected):
    profile = TomographyAnalyzer().analyze(study(), (probe(axis),), (outcome(axis),))
    assert expected in profile.dispositions and profile.certification_allowed is False


def test_verifier_plus_sham_success_is_nonspecific_not_promotable():
    targeted = probe(TomographyAxis.VERIFIER_FEEDBACK, probe_id="verify", control_intervention_id="sham")
    sham = probe(TomographyAxis.GENERIC_RETRY_CONTROL, probe_id="sham", intervention_id="sham")
    outs = (outcome(TomographyAxis.VERIFIER_FEEDBACK, probe_id="verify", replay_result_id="r1"),
        outcome(TomographyAxis.GENERIC_RETRY_CONTROL, probe_id="sham", replay_result_id="r2"))
    profile = TomographyAnalyzer().analyze(study(probe_ids=("verify", "sham"), projected_calls=2), (targeted, sham), outs)
    assert TomographyDisposition.NONSPECIFIC_RETRY_EFFECT in profile.dispositions
    assert profile.promotion_allowed is False


def test_targeted_recovery_beats_generic_retry_control():
    target = probe(TomographyAxis.TARGETED_RECOVERY, probe_id="target", control_intervention_id="control")
    control = probe(TomographyAxis.GENERIC_RETRY_CONTROL, probe_id="control", intervention_id="control")
    outs = (outcome(TomographyAxis.TARGETED_RECOVERY, probe_id="target", replay_result_id="r1"),
        outcome(TomographyAxis.GENERIC_RETRY_CONTROL, success=False, probe_id="control", replay_result_id="r2"))
    base_study = study(probe_ids=("target", "control"), projected_calls=2)
    profile = TomographyAnalyzer().analyze(base_study, (target, control), outs)
    assert TomographyDisposition.RECOVERY_POLICY_DEFICIT in profile.dispositions
    assert profile.route_back_stage is None and profile.promotion_allowed is False
    movement = TomographyAnalyzer().analyze(base_study, (target, control), outs, causal_movement_earned=True)
    assert movement.route_back_stage == "stage4" and movement.promotion_allowed is True


def test_skill_requires_related_case_evidence_before_stage4_routeback():
    p = probe(TomographyAxis.SKILL_PROCEDURE)
    weak = TomographyAnalyzer().analyze(study(), (p,), (outcome(TomographyAxis.SKILL_PROCEDURE),))
    assert weak.dispositions == (TomographyDisposition.UNRESOLVED,)
    strong = TomographyAnalyzer().analyze(study(), (p,), (outcome(TomographyAxis.SKILL_PROCEDURE),), skill_related_success_count=2)
    assert TomographyDisposition.SKILL_DEFICIT in strong.dispositions
    assert strong.route_back_stage is None and strong.promotion_allowed is False
    movement = TomographyAnalyzer().analyze(study(), (p,), (outcome(TomographyAxis.SKILL_PROCEDURE),),
        skill_related_success_count=2, causal_movement_earned=True)
    assert movement.route_back_stage == "stage4" and movement.promotion_allowed is True


def test_protected_regression_is_immediate_veto():
    profile = TomographyAnalyzer().analyze(study(), (probe(protected=True),),
        (outcome(protected_regression=True),))
    assert profile.promotion_allowed is False
    assert profile.stop_reason is TomographyStopReason.PROTECTED_NEGATIVE_TRANSFER


def test_external_supports_exhausted_yields_model_internal_residual():
    p = probe(TomographyAxis.TOOL_RESULT_INTERPRETATION)
    profile = TomographyAnalyzer().analyze(study(), (p,), (outcome(TomographyAxis.TOOL_RESULT_INTERPRETATION, success=False),),
        external_supports_exhausted=True)
    assert TomographyDisposition.MODEL_INTERNAL_RESIDUAL in profile.dispositions
    assert profile.model_internal_boundary is True and profile.promotion_allowed is False


def test_replay_compiler_uses_existing_replay_request_contract_only():
    intervention = InterventionDefinition.create(hypothesis_id="hyp-1", failure_snapshot_id="failure-1",
        parent_state_hash=SHA, kind=InterventionKind.TOOL, label="tool availability",
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        overrides={"request_envelopes.0.messages.0.content": "with deterministic tool evidence"},
        expected_causal_implication="tool availability separates the failure")
    p = probe(intervention_id=intervention.intervention_id, changed_dimensions=intervention.changed_dimensions)
    request = TomographyReplayCompiler.compile_request(study(), p, intervention,
        root_failure_snapshot_id="failure-root", source_model_id="qwen", source_model_digest="digest-1",
        request_id="request-1")
    assert request.metadata["tomography_study_id"] == "study-1"
    assert request.metadata["tomography_probe_id"] == "probe-1"
    assert request.changed_dimensions == intervention.changed_dimensions
    assert "raw_response" not in json.dumps(dict(request.metadata)).lower()


def test_tomography_store_is_append_only_metadata_and_rejects_duplicate_logical_ids(tmp_path):
    store = TomographyEvidenceStore(tmp_path)
    s, p, o = study(), probe(), outcome()
    store.append_study(s); store.append_probe(p); store.append_outcome(o)
    store.append_profile(TomographyAnalyzer().analyze(s, (p,), (o,)))
    report = store.validate()
    assert report.ok and report.record_count == 4
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (store.studies_path, store.outcomes_path, store.assessments_path)
    )
    assert "raw_response" not in text and "exposed_thinking" not in text
    with pytest.raises(ValueError, match="duplicate"):
        store.append_probe(p)


def test_failed_probe_keeps_child_snapshot_reference_in_metadata_store(tmp_path):
    store = TomographyEvidenceStore(tmp_path)
    store.append_study(study()); store.append_probe(probe()); store.append_outcome(outcome(success=False))
    assert store.outcomes()[0].child_failure_snapshot_id == "child-1"
