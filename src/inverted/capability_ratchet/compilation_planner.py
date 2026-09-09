"""Deterministic Stage-8 cheapest-owner planning with zero model calls."""

from __future__ import annotations

from .compilation_core import (
    CompilationCandidate,
    CompilationDisposition,
    CompilationKind,
    CompilationPlan,
    CompilationPolicy,
)


class CompilationPlanner:
    """Select the cheapest evidence-supported durable owner for a candidate."""

    def __init__(self, policy: CompilationPolicy | None = None) -> None:
        if policy is None:
            policy = CompilationPolicy()
        if not isinstance(policy, CompilationPolicy):
            raise TypeError("policy must be CompilationPolicy")
        self.policy = policy

    def plan(self, candidate: CompilationCandidate) -> CompilationPlan:
        if not isinstance(candidate, CompilationCandidate):
            raise TypeError("candidate must be CompilationCandidate")

        supported = frozenset(candidate.supported_kinds)
        selected: CompilationKind | None = None
        for kind in self.policy.owner_order:
            if kind in supported:
                selected = kind
                break
        if selected is None:
            raise ValueError("candidate has no supported compilation owner")

        selected_index = self.policy.owner_order.index(selected)
        rejected_cheaper: dict[str, str] = {}
        for cheaper in self.policy.owner_order[:selected_index]:
            if cheaper in supported:
                # This is unreachable for the first supported owner, but keeps the
                # invariant explicit if policy construction changes later.
                continue
            reason = candidate.excluded_cheaper_kinds.get(cheaper.value)
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"cheaper owner {cheaper.value} must be explicitly ruled out by evidence"
                )
            rejected_cheaper[cheaper.value] = reason

        if (
            selected is CompilationKind.REASONING_POLICY
            and not candidate.operating_surface_profile_id
        ):
            raise ValueError(
                "REASONING_POLICY requires operating-surface evidence"
            )

        if selected is CompilationKind.FINE_TUNE_CANDIDATE:
            if not candidate.model_internal_residual:
                raise ValueError(
                    "FINE_TUNE_CANDIDATE requires a resolved model-internal residual"
                )
            if not candidate.tomography_assessment_id:
                raise ValueError(
                    "FINE_TUNE_CANDIDATE requires a Stage-7 tomography assessment"
                )

        if selected in {
            CompilationKind.ESCALATION_POLICY,
            CompilationKind.SAFE_STOP_BOUNDARY,
        } and not candidate.model_internal_residual:
            raise ValueError(
                f"{selected.value} requires a resolved model-internal/external ownership boundary"
            )

        if selected is CompilationKind.FINE_TUNE_CANDIDATE:
            disposition = CompilationDisposition.FINE_TUNE_CANDIDATE
        elif selected is CompilationKind.ESCALATION_POLICY:
            disposition = CompilationDisposition.ESCALATION_CANDIDATE
        elif selected is CompilationKind.SAFE_STOP_BOUNDARY:
            disposition = CompilationDisposition.SAFE_STOP_BOUNDARY
        else:
            disposition = CompilationDisposition.COMPILED

        return CompilationPlan.create(
            candidate_id=candidate.candidate_id,
            selected_kind=selected,
            rejected_cheaper_kinds=rejected_cheaper,
            evidence_refs=candidate.evidence_refs,
            expected_disposition=disposition,
        )
