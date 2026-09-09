from __future__ import annotations

import pytest

from inverted.capability_ratchet.causal_core import InterventionDefinition, InterventionKind
from inverted.capability_ratchet.core import Partition, ReplayMode
from inverted.capability_ratchet.tomography_core import TomographyAxis, TomographyProbeSpec, TomographyStatus, TomographyStudy
from inverted.capability_ratchet.tomography_replay import TomographyReplayCompiler

SHA = "a" * 64


def _study(*, decisions=("D6", "D8"), probe_id="probe-1") -> TomographyStudy:
    return TomographyStudy(
        study_id="study-1",
        failure_snapshot_id="failure-parent",
        parent_state_hash=SHA,
        partition=Partition.DEVELOPMENT,
        decision_ids=tuple(decisions),
        candidate_axes=(TomographyAxis.TOOL_EXECUTION_RESULT,),
        baseline_evidence_refs=("baseline-1",),
        probe_ids=(probe_id,),
        max_new_probes=3,
        projected_calls=1,
        status=TomographyStatus.PLANNED,
    )


def _probe(axis: TomographyAxis, *, dimension="request_envelopes.0.messages.0.content") -> TomographyProbeSpec:
    intervention = InterventionDefinition.create(
        hypothesis_id="hyp-1",
        failure_snapshot_id="failure-parent",
        parent_state_hash=SHA,
        kind=(
            InterventionKind.TOOL
            if axis in {
                TomographyAxis.TOOL_AVAILABILITY,
                TomographyAxis.TOOL_SELECTION,
                TomographyAxis.TOOL_ARGUMENTS,
                TomographyAxis.TOOL_EXECUTION_RESULT,
                TomographyAxis.TOOL_RESULT_INTERPRETATION,
            }
            else InterventionKind.SKILL
            if axis in {TomographyAxis.SKILL_TRIGGER, TomographyAxis.SKILL_PROCEDURE}
            else InterventionKind.ESCALATION
            if axis is TomographyAxis.ESCALATION_REFERENCE
            else InterventionKind.VERIFICATION_RECOVERY
        ),
        label=f"stage7 {axis.value}",
        changed_dimensions=(dimension,),
        overrides={dimension: f"registered delta for {axis.value}"},
        expected_causal_implication=f"separate ownership at {axis.value}",
    )
    probe = TomographyProbeSpec(
        probe_id="probe-1",
        study_id="study-1",
        axis=axis,
        intervention_id=intervention.intervention_id,
        control_intervention_id="control-1" if axis is TomographyAxis.GENERIC_RETRY_CONTROL else None,
        changed_dimensions=(dimension,),
        expected_implication=f"diagnose {axis.value}",
        projected_calls=1,
        protected=False,
    )
    return probe, intervention


def _compile(axis: TomographyAxis, **kwargs):
    probe, intervention = _probe(axis)
    return TomographyReplayCompiler.compile_request(
        _study(),
        probe,
        intervention,
        root_failure_snapshot_id="failure-root",
        source_model_id="qwen",
        source_model_digest="digest-1",
        request_id="request-1",
        **kwargs,
    )


def test_replay_metadata_carries_full_stage7_decision_and_evidence_contract() -> None:
    request = _compile(
        TomographyAxis.TOOL_EXECUTION_RESULT,
        evidence_status="REUSED",
        evidence_provenance_refs=("tool-result-sha256:abc",),
    )
    assert request.mode is ReplayMode.COUNTERFACTUAL
    assert request.decision_id == "D6"
    assert request.metadata["tomography_decision_ids"] == ("D6", "D8")
    assert request.metadata["tomography_expected_implication"] == "diagnose TOOL_EXECUTION_RESULT"
    assert request.metadata["tomography_evidence_status"] == "REUSED"
    assert request.metadata["tomography_generic_retry_control"] is False
    assert request.metadata["tomography_evidence_provenance_refs"] == ("tool-result-sha256:abc",)
    assert request.metadata["tomography_state_delta_kind"] == "SUPPLIED_TOOL_RESULT"
    assert request.metadata["stage7_certification_allowed"] is False


def test_generic_retry_is_explicitly_labeled_control_not_recovery() -> None:
    request = _compile(TomographyAxis.GENERIC_RETRY_CONTROL, evidence_status="NEW")
    assert request.metadata["tomography_generic_retry_control"] is True
    assert request.metadata["tomography_state_delta_kind"] == "GENERIC_RETRY_CONTROL"


@pytest.mark.parametrize(
    "axis,expected",
    [
        (TomographyAxis.TOOL_AVAILABILITY, "TOOL_SCHEMA_OR_MENU"),
        (TomographyAxis.TOOL_SELECTION, "FORCED_TOOL_SELECTION"),
        (TomographyAxis.TOOL_ARGUMENTS, "FORCED_TOOL_ARGUMENTS"),
        (TomographyAxis.TOOL_EXECUTION_RESULT, "SUPPLIED_TOOL_RESULT"),
        (TomographyAxis.TOOL_RESULT_INTERPRETATION, "TOOL_RESULT_INTERPRETATION"),
        (TomographyAxis.VERIFIER_VISIBILITY, "VERIFIER_VISIBILITY"),
        (TomographyAxis.VERIFIER_FEEDBACK, "VERIFIER_FEEDBACK"),
        (TomographyAxis.TARGETED_RECOVERY, "TARGETED_RECOVERY_STATE"),
        (TomographyAxis.SKILL_TRIGGER, "SKILL_TRIGGER"),
        (TomographyAxis.SKILL_PROCEDURE, "SKILL_PROCEDURE"),
        (TomographyAxis.ESCALATION_REFERENCE, "ESCALATION_REFERENCE"),
    ],
)
def test_each_tomography_axis_has_explicit_state_delta_semantics(axis: TomographyAxis, expected: str) -> None:
    kwargs = {}
    if axis is TomographyAxis.TOOL_EXECUTION_RESULT:
        kwargs["evidence_provenance_refs"] = ("result-ref-1",)
    request = _compile(axis, **kwargs)
    assert request.metadata["tomography_state_delta_kind"] == expected
    assert request.metadata["tomography_changed_dimensions"] == request.changed_dimensions


def test_supplied_tool_result_requires_observable_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        _compile(TomographyAxis.TOOL_EXECUTION_RESULT)


def test_evidence_status_is_frozen_to_new_or_reused() -> None:
    with pytest.raises(ValueError, match="evidence_status"):
        _compile(TomographyAxis.TOOL_SELECTION, evidence_status="MAYBE")


def test_non_cognition_stage7_probe_cannot_change_inference_profile() -> None:
    probe, intervention = _probe(
        TomographyAxis.TOOL_SELECTION,
        dimension="request_envelopes.0.inference_profile.temperature",
    )
    with pytest.raises(ValueError, match="inference profile"):
        TomographyReplayCompiler.compile_request(
            _study(),
            probe,
            intervention,
            root_failure_snapshot_id="failure-root",
            source_model_id="qwen",
            source_model_digest="digest-1",
            request_id="request-1",
        )
