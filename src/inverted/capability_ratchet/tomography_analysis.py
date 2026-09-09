"""Deterministic Stage-7 tomography disposition analysis."""

from __future__ import annotations

from .tomography_core import (
    TomographyAxis,
    TomographyDisposition,
    TomographyOutcome,
    TomographyProbe,
    TomographyProfile,
    TomographyStopReason,
    TomographyStudy,
    stable_id,
)


_TOOL_DISPOSITIONS = {
    TomographyAxis.TOOL_AVAILABILITY: TomographyDisposition.TOOL_REQUIRED,
    TomographyAxis.TOOL_SELECTION: TomographyDisposition.TOOL_SELECTION_DEFICIT,
    TomographyAxis.TOOL_ARGUMENTS: TomographyDisposition.TOOL_ARGUMENT_DEFICIT,
    TomographyAxis.TOOL_EXECUTION_RESULT: TomographyDisposition.TOOL_EXECUTION_FAILURE,
    TomographyAxis.TOOL_RESULT_INTERPRETATION: TomographyDisposition.TOOL_INTERPRETATION_DEFICIT,
}
_SKILL_AXES = {
    TomographyAxis.SKILL_TRIGGER,
    TomographyAxis.SKILL_PROCEDURE,
}
_MOVEMENT_ELIGIBLE_DISPOSITIONS = {
    TomographyDisposition.TOOL_REQUIRED,
    TomographyDisposition.TOOL_SELECTION_DEFICIT,
    TomographyDisposition.TOOL_ARGUMENT_DEFICIT,
    TomographyDisposition.TOOL_EXECUTION_FAILURE,
    TomographyDisposition.TOOL_INTERPRETATION_DEFICIT,
    TomographyDisposition.VERIFIER_SUFFICIENT,
    TomographyDisposition.RECOVERY_SUFFICIENT,
    TomographyDisposition.SKILL_CANDIDATE,
}


class TomographyAnalyzer:
    """Map matched Stage-7 outcomes to explicit, non-certifying dispositions."""

    def analyze(
        self,
        study: TomographyStudy,
        probes: tuple[TomographyProbe, ...],
        outcomes: tuple[TomographyOutcome, ...],
        *,
        skill_related_success_count: int = 0,
        external_supports_exhausted: bool = False,
        causal_movement_earned: bool = False,
        safe_stop_required: bool = False,
    ) -> TomographyProfile:
        if not isinstance(study, TomographyStudy):
            raise TypeError("study must be TomographyStudy")
        probes = tuple(probes)
        outcomes = tuple(outcomes)
        if any(item.study_id != study.study_id for item in probes):
            raise ValueError("probe study lineage mismatch")
        if any(item.study_id != study.study_id for item in outcomes):
            raise ValueError("outcome study lineage mismatch")
        by_probe = {item.probe_id: item for item in probes}
        if len(by_probe) != len(probes):
            raise ValueError("duplicate probe IDs")
        outcome_by_probe = {item.probe_id: item for item in outcomes}
        if len(outcome_by_probe) != len(outcomes):
            raise ValueError("duplicate outcome probe IDs")
        if any(probe_id not in by_probe for probe_id in outcome_by_probe):
            raise ValueError("outcome references unknown tomography probe")
        if not isinstance(skill_related_success_count, int) or isinstance(skill_related_success_count, bool) or skill_related_success_count < 0:
            raise ValueError("skill_related_success_count must be non-negative")
        for name, value in (
            ("external_supports_exhausted", external_supports_exhausted),
            ("causal_movement_earned", causal_movement_earned),
            ("safe_stop_required", safe_stop_required),
        ):
            if type(value) is not bool:
                raise TypeError(f"{name} must be boolean")

        evidence_refs = tuple(dict.fromkeys(item.replay_result_id for item in outcomes))
        if not evidence_refs:
            evidence_refs = study.baseline_evidence_refs

        if any(item.protected_regression for item in outcomes):
            return self._profile(
                study, (TomographyDisposition.UNRESOLVED,), evidence_refs,
                promotion=False,
                stop_reason=TomographyStopReason.PROTECTED_NEGATIVE_TRANSFER,
            )

        successful_axes = {
            by_probe[item.probe_id].axis
            for item in outcomes
            if item.success and item.probe_id in by_probe
        }
        dispositions: list[TomographyDisposition] = []

        # Tool ownership is admissible only from a successful targeted probe.
        for axis, disposition in _TOOL_DISPOSITIONS.items():
            if axis in successful_axes:
                dispositions.append(disposition)

        generic_success = TomographyAxis.GENERIC_RETRY_CONTROL in successful_axes
        verifier_success = TomographyAxis.VERIFIER_FEEDBACK in successful_axes
        targeted_recovery_success = TomographyAxis.TARGETED_RECOVERY in successful_axes
        if verifier_success:
            dispositions.append(
                TomographyDisposition.UNRESOLVED
                if generic_success else TomographyDisposition.VERIFIER_SUFFICIENT
            )
        if targeted_recovery_success:
            dispositions.append(
                TomographyDisposition.UNRESOLVED
                if generic_success else TomographyDisposition.RECOVERY_SUFFICIENT
            )
        if generic_success and not (verifier_success or targeted_recovery_success):
            dispositions.append(TomographyDisposition.UNRESOLVED)

        # Visibility proves only that verifier evidence can be exposed. It does not
        # prove feedback suffices to repair the failure.
        if TomographyAxis.VERIFIER_VISIBILITY in successful_axes and not verifier_success:
            dispositions.append(TomographyDisposition.UNRESOLVED)

        skill_success = any(axis in successful_axes for axis in _SKILL_AXES)
        if skill_success:
            dispositions.append(
                TomographyDisposition.SKILL_CANDIDATE
                if skill_related_success_count >= 2
                else TomographyDisposition.UNRESOLVED
            )

        escalation_success = TomographyAxis.ESCALATION_REFERENCE in successful_axes
        if escalation_success:
            dispositions.append(
                TomographyDisposition.ESCALATION_CANDIDATE
                if external_supports_exhausted
                else TomographyDisposition.UNRESOLVED
            )

        # Collapse duplicates before evaluating the residual boundary.
        dispositions = list(dict.fromkeys(dispositions))
        specific_external_gain = any(
            item in _MOVEMENT_ELIGIBLE_DISPOSITIONS
            for item in dispositions
        )
        escalation_gain = TomographyDisposition.ESCALATION_CANDIDATE in dispositions

        model_internal = False
        stop_reason: TomographyStopReason | None = None
        if external_supports_exhausted and not specific_external_gain and not escalation_gain:
            if safe_stop_required:
                dispositions = [TomographyDisposition.SAFE_STOP_BOUNDARY]
            else:
                dispositions = [TomographyDisposition.MODEL_INTERNAL_RESIDUAL]
                model_internal = True
                stop_reason = TomographyStopReason.MODEL_INTERNAL_BOUNDARY

        if not dispositions:
            dispositions = [TomographyDisposition.UNRESOLVED]
        dispositions = list(dict.fromkeys(dispositions))

        promotion = bool(
            causal_movement_earned
            and any(item in _MOVEMENT_ELIGIBLE_DISPOSITIONS for item in dispositions)
            and not model_internal
        )
        return self._profile(
            study,
            tuple(dispositions),
            evidence_refs,
            promotion=promotion,
            model_internal=model_internal,
            stop_reason=stop_reason,
        )

    @staticmethod
    def _profile(
        study: TomographyStudy,
        dispositions: tuple[TomographyDisposition, ...],
        evidence_refs: tuple[str, ...],
        *,
        promotion: bool,
        model_internal: bool = False,
        stop_reason: TomographyStopReason | None = None,
    ) -> TomographyProfile:
        payload = {
            "study_id": study.study_id,
            "dispositions": [item.value for item in dispositions],
            "evidence_refs": list(evidence_refs),
            "model_internal": model_internal,
            "promotion_allowed": promotion,
            "route_back_stage": "stage4" if promotion else None,
            "stop_reason": None if stop_reason is None else stop_reason.value,
        }
        supported = tuple(
            f"stage7:{item.value}"
            for item in dispositions
            if item is not TomographyDisposition.UNRESOLVED
        )
        return TomographyProfile(
            profile_id=stable_id("tomography-profile", payload),
            study_id=study.study_id,
            dispositions=dispositions,
            supported_hypotheses=supported,
            falsified_hypotheses=(),
            evidence_refs=evidence_refs,
            next_decisions=study.decision_ids,
            route_back_stage="stage4" if promotion else None,
            model_internal_boundary=model_internal,
            promotion_allowed=promotion,
            certification_allowed=False,
            stop_reason=stop_reason,
        )
