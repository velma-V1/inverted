"""Compile Stage-7 tomography probes into canonical replay requests."""

from __future__ import annotations

from .causal_core import InterventionDefinition
from .core import ReplayMode, ReplayRequest
from .tomography_core import TomographyAxis, TomographyProbe, TomographyStudy


_STATE_DELTA_KIND = {
    TomographyAxis.TOOL_AVAILABILITY: "TOOL_SCHEMA_OR_MENU",
    TomographyAxis.TOOL_SELECTION: "FORCED_TOOL_SELECTION",
    TomographyAxis.TOOL_ARGUMENTS: "FORCED_TOOL_ARGUMENTS",
    TomographyAxis.TOOL_EXECUTION_RESULT: "SUPPLIED_TOOL_RESULT",
    TomographyAxis.TOOL_RESULT_INTERPRETATION: "TOOL_RESULT_INTERPRETATION",
    TomographyAxis.VERIFIER_VISIBILITY: "VERIFIER_VISIBILITY",
    TomographyAxis.VERIFIER_FEEDBACK: "VERIFIER_FEEDBACK",
    TomographyAxis.TARGETED_RECOVERY: "TARGETED_RECOVERY_STATE",
    TomographyAxis.GENERIC_RETRY_CONTROL: "GENERIC_RETRY_CONTROL",
    TomographyAxis.SKILL_PROCEDURE: "SKILL_PROCEDURE",
    TomographyAxis.SKILL_TRIGGER: "SKILL_TRIGGER",
    TomographyAxis.ESCALATION_REFERENCE: "ESCALATION_REFERENCE",
}


class TomographyReplayCompiler:
    """Pure compiler only; execution remains owned by the canonical ReplayExecutor."""

    @staticmethod
    def compile_request(
        study: TomographyStudy,
        probe: TomographyProbe,
        intervention: InterventionDefinition,
        *,
        root_failure_snapshot_id: str,
        source_model_id: str,
        source_model_digest: str,
        request_id: str,
        evidence_status: str = "NEW",
        evidence_provenance_refs: tuple[str, ...] = (),
    ) -> ReplayRequest:
        if not isinstance(study, TomographyStudy):
            raise TypeError("study must be TomographyStudy")
        if not isinstance(probe, TomographyProbe):
            raise TypeError("probe must be TomographyProbe")
        if not isinstance(intervention, InterventionDefinition):
            raise TypeError("intervention must be InterventionDefinition")
        if probe.study_id != study.study_id or probe.probe_id not in study.probe_ids:
            raise ValueError("probe is not registered in tomography study")
        if intervention.intervention_id != probe.intervention_id:
            raise ValueError("probe intervention differs from canonical intervention")
        if intervention.failure_snapshot_id != study.failure_snapshot_id:
            raise ValueError("intervention failure lineage differs from tomography study")
        if intervention.parent_state_hash != study.parent_state_hash:
            raise ValueError("intervention parent state differs from tomography study")
        if tuple(intervention.changed_dimensions) != tuple(probe.changed_dimensions):
            raise ValueError("probe changed dimensions differ from intervention")
        if intervention.projected_physical_calls < 1:
            raise ValueError("zero-call interventions do not compile to model replay")
        if probe.projected_calls != intervention.projected_physical_calls:
            raise ValueError("probe projected calls differ from intervention")
        for name, value in (
            ("root_failure_snapshot_id", root_failure_snapshot_id),
            ("source_model_id", source_model_id),
            ("source_model_digest", source_model_digest),
            ("request_id", request_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")

        if evidence_status not in {"NEW", "REUSED"}:
            raise ValueError("evidence_status must be NEW or REUSED")
        provenance_refs = tuple(evidence_provenance_refs)
        if any(not isinstance(ref, str) or not ref.strip() for ref in provenance_refs):
            raise ValueError("evidence provenance references must be non-blank strings")
        if probe.axis is TomographyAxis.TOOL_EXECUTION_RESULT and not provenance_refs:
            raise ValueError("supplied tool result requires observable provenance")

        # Stage 7 isolates external operating-surface mechanisms. It must not
        # silently turn a tool/verifier/recovery probe into a cognition change.
        for dimension in intervention.changed_dimensions:
            if "inference_profile" in dimension.lower():
                raise ValueError("Stage-7 non-cognition probe cannot change inference profile")

        try:
            state_delta_kind = _STATE_DELTA_KIND[probe.axis]
        except KeyError as exc:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError(f"unsupported tomography axis: {probe.axis}") from exc

        return ReplayRequest(
            replay_request_id=request_id,
            failure_snapshot_id=root_failure_snapshot_id,
            parent_failure_snapshot_id=study.failure_snapshot_id,
            parent_state_hash=study.parent_state_hash,
            decision_id=study.decision_ids[0],
            hypothesis_id=intervention.hypothesis_id,
            expected_causal_implication=probe.expected_implication,
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=source_model_id,
            source_model_digest=source_model_digest,
            target_model_id=source_model_id,
            target_model_digest=source_model_digest,
            partition=study.partition,
            changed_dimensions=intervention.changed_dimensions,
            intervention_id=intervention.intervention_id,
            overrides=intervention.overrides,
            metadata={
                "tomography_study_id": study.study_id,
                "tomography_probe_id": probe.probe_id,
                "tomography_axis": probe.axis.value,
                "tomography_decision_ids": tuple(study.decision_ids),
                "tomography_expected_implication": probe.expected_implication,
                "tomography_evidence_status": evidence_status,
                "tomography_evidence_provenance_refs": provenance_refs,
                "tomography_generic_retry_control": probe.axis is TomographyAxis.GENERIC_RETRY_CONTROL,
                "tomography_state_delta_kind": state_delta_kind,
                "tomography_changed_dimensions": tuple(intervention.changed_dimensions),
                "control_intervention_id": probe.control_intervention_id,
                "projected_physical_calls": probe.projected_calls,
                "protected": probe.protected,
                "stage7_certification_allowed": False,
            },
        )
