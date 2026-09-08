"""Bounded, existing-evidence-first planner for Stage-7 tomography."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .causal_core import DivergenceClass
from .core import Partition
from .tomography_core import (
    TomographyAxis,
    TomographyProbe,
    TomographyStatus,
    TomographyStopReason,
    TomographyStudy,
    stable_id,
)


_AXIS_LADDERS: dict[DivergenceClass, tuple[TomographyAxis, ...]] = {
    DivergenceClass.TOOL_CAPABILITY: (TomographyAxis.TOOL_AVAILABILITY,),
    DivergenceClass.TOOL_SELECTION: (
        TomographyAxis.TOOL_AVAILABILITY,
        TomographyAxis.TOOL_SELECTION,
    ),
    DivergenceClass.TOOL_ARGUMENTS: (
        TomographyAxis.TOOL_AVAILABILITY,
        TomographyAxis.TOOL_SELECTION,
        TomographyAxis.TOOL_ARGUMENTS,
    ),
    DivergenceClass.TOOL_INTERPRETATION: (
        TomographyAxis.TOOL_AVAILABILITY,
        TomographyAxis.TOOL_SELECTION,
        TomographyAxis.TOOL_ARGUMENTS,
        TomographyAxis.TOOL_RESULT_INTERPRETATION,
    ),
    DivergenceClass.VERIFIER_FEEDBACK: (TomographyAxis.VERIFIER_FEEDBACK,),
    DivergenceClass.RECOVERY_POLICY: (
        TomographyAxis.TARGETED_RECOVERY,
        TomographyAxis.GENERIC_RETRY_CONTROL,
    ),
    DivergenceClass.SKILL_DEFICIT: (
        TomographyAxis.SKILL_TRIGGER,
        TomographyAxis.SKILL_PROCEDURE,
        TomographyAxis.SKILL_EVIDENCE_REQUIREMENT,
        TomographyAxis.SKILL_VERIFICATION_RULE,
    ),
    DivergenceClass.MODEL_CAPABILITY_LIMIT: (
        TomographyAxis.STRONGER_MODEL_ESCALATION_CONTROL,
    ),
}


@dataclass(frozen=True)
class TomographyPlan:
    study: TomographyStudy
    probes: tuple[TomographyProbe, ...]
    model_calls: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "probes", tuple(self.probes))
        if not isinstance(self.model_calls, int) or isinstance(self.model_calls, bool) or self.model_calls < 0:
            raise ValueError("model_calls must be a non-negative integer")
        if self.model_calls != 0:
            raise ValueError("Stage-7 planning must be zero-model-call")
        if tuple(item.probe_id for item in self.probes) != self.study.probe_ids:
            raise ValueError("plan probes must exactly match study probe_ids")


class TomographyPlanner:
    """Choose the smallest registered contrast that can change a named decision."""

    @staticmethod
    def _stopped(
        *, failure_snapshot_id: str, parent_state_hash: str, partition: Partition,
        decision_ids: tuple[str, ...], baseline_evidence_refs: tuple[str, ...],
        reason: TomographyStopReason, max_new_probes: int,
        candidate_axes: tuple[TomographyAxis, ...] = (),
    ) -> TomographyPlan:
        identity = {
            "failure_snapshot_id": failure_snapshot_id,
            "parent_state_hash": parent_state_hash,
            "decisions": list(decision_ids),
            "reason": reason.value,
        }
        study = TomographyStudy(
            study_id=stable_id("tomography-study", identity),
            failure_snapshot_id=failure_snapshot_id,
            parent_state_hash=parent_state_hash,
            partition=partition,
            decision_ids=decision_ids,
            candidate_axes=candidate_axes,
            baseline_evidence_refs=baseline_evidence_refs,
            probe_ids=(),
            max_new_probes=max_new_probes,
            projected_calls=0,
            status=TomographyStatus.STOPPED,
            stop_reason=reason,
        )
        return TomographyPlan(study=study, probes=(), model_calls=0)

    def plan(
        self,
        *,
        failure_snapshot_id: str,
        parent_state_hash: str,
        partition: Partition,
        divergence: DivergenceClass,
        decision_ids: tuple[str, ...],
        baseline_evidence_refs: tuple[str, ...],
        intervention_ids: Mapping[TomographyAxis, str],
        changed_dimensions: Mapping[TomographyAxis, tuple[str, ...]],
        resolved_axes: tuple[TomographyAxis, ...] = (),
        max_new_probes: int = 3,
        extension_authorized: bool = False,
        external_supports_exhausted: bool = False,
        deterministic_scoring: bool = True,
        baseline_linked: bool = True,
        parent_state_resolves: bool = True,
        protected_direct_solved_veto: bool = False,
        protected_partition_authorized: bool = False,
    ) -> TomographyPlan:
        part = partition if isinstance(partition, Partition) else Partition(partition)
        kind = divergence if isinstance(divergence, DivergenceClass) else DivergenceClass(divergence)
        if not isinstance(max_new_probes, int) or isinstance(max_new_probes, bool) or max_new_probes < 1:
            raise ValueError("max_new_probes must be at least 1")
        if max_new_probes > 3 and not extension_authorized:
            raise ValueError("more than three Stage-7 probes requires explicit extension authorization")
        decisions = tuple(decision_ids)
        evidence = tuple(baseline_evidence_refs)
        if not decisions or not evidence:
            raise ValueError("decision_ids and baseline_evidence_refs are required")

        axes = _AXIS_LADDERS.get(kind)
        if axes is None:
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=TomographyStopReason.NO_ELIGIBLE_RESIDUALS,
                max_new_probes=max_new_probes,
            )
        if part in {Partition.FRESH, Partition.SEALED} and not protected_partition_authorized:
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=TomographyStopReason.INSUFFICIENT_OBSERVABLE_EVIDENCE,
                max_new_probes=max_new_probes, candidate_axes=axes,
            )
        if protected_direct_solved_veto:
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=TomographyStopReason.PROTECTED_NEGATIVE_TRANSFER,
                max_new_probes=max_new_probes, candidate_axes=axes,
            )
        if not (deterministic_scoring and baseline_linked and parent_state_resolves):
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=TomographyStopReason.INSUFFICIENT_OBSERVABLE_EVIDENCE,
                max_new_probes=max_new_probes, candidate_axes=axes,
            )
        if kind is DivergenceClass.MODEL_CAPABILITY_LIMIT:
            reason = (
                TomographyStopReason.MODEL_INTERNAL_BOUNDARY
                if external_supports_exhausted
                else TomographyStopReason.INSUFFICIENT_OBSERVABLE_EVIDENCE
            )
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=reason, max_new_probes=max_new_probes, candidate_axes=axes,
            )

        resolved = {item if isinstance(item, TomographyAxis) else TomographyAxis(item) for item in resolved_axes}
        remaining = tuple(axis for axis in axes if axis not in resolved)
        if not remaining:
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=TomographyStopReason.DECISION_ALREADY_RESOLVED,
                max_new_probes=max_new_probes, candidate_axes=axes,
            )

        selected: list[TomographyAxis] = []
        for axis in remaining:
            if axis not in intervention_ids or axis not in changed_dimensions:
                # Existing-evidence-first ladder cannot skip an unresolved prerequisite.
                if axis in {
                    TomographyAxis.TOOL_AVAILABILITY,
                    TomographyAxis.TOOL_SELECTION,
                    TomographyAxis.TOOL_ARGUMENTS,
                }:
                    break
                continue
            selected.append(axis)
            if len(selected) == max_new_probes:
                break
        if TomographyAxis.GENERIC_RETRY_CONTROL in selected and TomographyAxis.TARGETED_RECOVERY not in selected:
            selected.remove(TomographyAxis.GENERIC_RETRY_CONTROL)
        if not selected:
            return self._stopped(
                failure_snapshot_id=failure_snapshot_id, parent_state_hash=parent_state_hash,
                partition=part, decision_ids=decisions, baseline_evidence_refs=evidence,
                reason=TomographyStopReason.NO_DIAGNOSTIC_CONTRAST,
                max_new_probes=max_new_probes, candidate_axes=remaining,
            )

        study_seed = {
            "failure_snapshot_id": failure_snapshot_id,
            "parent_state_hash": parent_state_hash,
            "decisions": list(decisions),
            "axes": [axis.value for axis in selected],
        }
        study_id = stable_id("tomography-study", study_seed)
        probes: list[TomographyProbe] = []
        target_recovery_id = intervention_ids.get(TomographyAxis.TARGETED_RECOVERY)
        generic_control_id = intervention_ids.get(TomographyAxis.GENERIC_RETRY_CONTROL)
        verifier_control_id = intervention_ids.get(TomographyAxis.GENERIC_RETRY_CONTROL)
        for axis in selected:
            intervention_id = intervention_ids[axis]
            control_id = None
            if axis is TomographyAxis.TARGETED_RECOVERY:
                control_id = generic_control_id
            elif axis is TomographyAxis.VERIFIER_FEEDBACK:
                control_id = verifier_control_id
            elif axis is TomographyAxis.GENERIC_RETRY_CONTROL:
                control_id = target_recovery_id
            seed = {"study_id": study_id, "axis": axis.value, "intervention_id": intervention_id}
            probes.append(TomographyProbe(
                probe_id=stable_id("tomography-probe", seed),
                study_id=study_id,
                axis=axis,
                intervention_id=intervention_id,
                control_intervention_id=control_id,
                changed_dimensions=tuple(changed_dimensions[axis]),
                expected_implication=f"separate {kind.value} using only the registered {axis.value} dimension",
                projected_calls=1,
                protected=False,
            ))
        projected = sum(item.projected_calls for item in probes)
        study = TomographyStudy(
            study_id=study_id,
            failure_snapshot_id=failure_snapshot_id,
            parent_state_hash=parent_state_hash,
            partition=part,
            decision_ids=decisions,
            candidate_axes=remaining,
            baseline_evidence_refs=evidence,
            probe_ids=tuple(item.probe_id for item in probes),
            max_new_probes=max_new_probes,
            projected_calls=projected,
            status=TomographyStatus.PLANNED,
        )
        return TomographyPlan(study=study, probes=tuple(probes), model_calls=0)
