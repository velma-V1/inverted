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
    TomographyAxis.TOOL_RESULT_INTERPRETATION: TomographyDisposition.TOOL_INTERPRETATION_DEFICIT,
}
_SKILL_AXES = {
    TomographyAxis.SKILL_TRIGGER,
    TomographyAxis.SKILL_PROCEDURE,
    TomographyAxis.SKILL_EVIDENCE_REQUIREMENT,
    TomographyAxis.SKILL_VERIFICATION_RULE,
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
        if type(external_supports_exhausted) is not bool:
            raise TypeError("external_supports_exhausted must be boolean")

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

        # Tool ladder dispositions are admissible only from a successful targeted probe.
        for axis, disposition in _TOOL_DISPOSITIONS.items():
            if axis in successful_axes:
                dispositions.append(disposition)

        generic_success = TomographyAxis.GENERIC_RETRY_CONTROL in successful_axes
        verifier_success = TomographyAxis.VERIFIER_FEEDBACK in successful_axes
        targeted_recovery_success = TomographyAxis.TARGETED_RECOVERY in successful_axes
        if verifier_success:
            dispositions.append(
                TomographyDisposition.NONSPECIFIC_RETRY_EFFECT
                if generic_success else TomographyDisposition.VERIFIER_RECOVERABLE
            )
        if targeted_recovery_success:
            dispositions.append(
                TomographyDisposition.NONSPECIFIC_RETRY_EFFECT
                if generic_success else TomographyDisposition.RECOVERY_POLICY_DEFICIT
            )
        if generic_success and not (verifier_success or targeted_recovery_success):
            dispositions.append(TomographyDisposition.NONSPECIFIC_RETRY_EFFECT)

        skill_success = any(axis in successful_axes for axis in _SKILL_AXES)
        if skill_success:
            if skill_related_success_count >= 2:
                dispositions.append(TomographyDisposition.SKILL_DEFICIT)
            else:
                dispositions.append(TomographyDisposition.UNRESOLVED)

        # A model-internal boundary is never inferred from one failure. It requires an
        # explicit caller assertion that admissible external supports were exhausted.
        any_external_gain = any(
            item not in {
                TomographyDisposition.UNRESOLVED,
                TomographyDisposition.NONSPECIFIC_RETRY_EFFECT,
            }
            for item in dispositions
        )
        model_internal = bool(external_supports_exhausted and not any_external_gain)
        if model_internal:
            dispositions = [TomographyDisposition.MODEL_INTERNAL_RESIDUAL]

        if not dispositions:
            dispositions = [TomographyDisposition.UNRESOLVED]
        dispositions = list(dict.fromkeys(dispositions))

        nonspecific_only = all(
            item in {TomographyDisposition.UNRESOLVED, TomographyDisposition.NONSPECIFIC_RETRY_EFFECT}
            for item in dispositions
        )
        promotion = bool(not model_internal and not nonspecific_only)
        return self._profile(
            study,
            tuple(dispositions),
            evidence_refs,
            promotion=promotion,
            model_internal=model_internal,
            stop_reason=(TomographyStopReason.MODEL_INTERNAL_BOUNDARY if model_internal else None),
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
            "stop_reason": None if stop_reason is None else stop_reason.value,
        }
        supported = tuple(
            f"stage7:{item.value}"
            for item in dispositions
            if item not in {TomographyDisposition.UNRESOLVED, TomographyDisposition.NONSPECIFIC_RETRY_EFFECT}
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
