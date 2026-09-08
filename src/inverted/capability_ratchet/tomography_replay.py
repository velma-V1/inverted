"""Compile Stage-7 tomography probes into canonical replay requests."""

from __future__ import annotations

from .causal_core import InterventionDefinition
from .core import ReplayMode, ReplayRequest
from .tomography_core import TomographyProbe, TomographyStudy


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
                "control_intervention_id": probe.control_intervention_id,
                "projected_physical_calls": probe.projected_calls,
                "protected": probe.protected,
                "stage7_certification_allowed": False,
            },
        )
