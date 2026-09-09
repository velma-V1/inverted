"""Pure, zero-inference compilation of generalized mechanisms into durable artifacts."""

from __future__ import annotations

from typing import Any

from .compilation_core import (
    CompilationCandidate,
    CompilationDisposition,
    CompilationKind,
    CompilationPlan,
    CompiledCapability,
)
from .compilation_planner import CompilationPlanner


_HANDOFFS = {
    CompilationKind.DETERMINISTIC_RULE: "STAGE10_OR_STAGE11",
    CompilationKind.STATE_REPRESENTATION: "STAGE10_OR_STAGE11",
    CompilationKind.FORMATTER_PARSER_VALIDATOR: "STAGE10_OR_STAGE11",
    CompilationKind.TOOL_POLICY: "STAGE10_OR_STAGE11",
    CompilationKind.SKILL_POLICY: "STAGE10_OR_STAGE11",
    CompilationKind.REASONING_POLICY: "STAGE10_OR_STAGE11",
    CompilationKind.VERIFIER_RECOVERY_POLICY: "STAGE10_OR_STAGE11",
    CompilationKind.FINE_TUNE_CANDIDATE: "STAGE9",
    CompilationKind.ESCALATION_POLICY: "ESCALATION_POLICY_RESEARCH",
    CompilationKind.SAFE_STOP_BOUNDARY: "STAGE11_BOUNDARY_CONFIRMATION",
}


class CapabilityCompiler:
    """Compile evidence into immutable capability metadata; never execute it."""

    def __init__(self, store: Any, *, planner: CompilationPlanner | None = None) -> None:
        required = (
            "validate",
            "candidates",
            "decisions",
            "capabilities",
            "append_candidate",
            "append_decision",
            "append_capability",
        )
        missing = [name for name in required if not callable(getattr(store, name, None))]
        if missing:
            raise TypeError(f"store must expose {', '.join(missing)}")
        if planner is None:
            planner = CompilationPlanner()
        if not isinstance(planner, CompilationPlanner):
            raise TypeError("planner must be CompilationPlanner")
        self.store = store
        self.planner = planner

    @staticmethod
    def _revalidate_candidate(candidate: CompilationCandidate) -> CompilationCandidate:
        if not isinstance(candidate, CompilationCandidate):
            raise TypeError("candidate must be CompilationCandidate")
        # Reconstruct through the frozen contract to catch object.__setattr__ tampering,
        # hidden-oracle triggers, raw payload duplication, or stale content IDs.
        return CompilationCandidate(
            candidate_id=candidate.candidate_id,
            failure_snapshot_id=candidate.failure_snapshot_id,
            mechanism_id=candidate.mechanism_id,
            generalization_profile_id=candidate.generalization_profile_id,
            prior_generalized_evidence_ref=candidate.prior_generalized_evidence_ref,
            generalization_class=candidate.generalization_class,
            mechanism_label_ids=candidate.mechanism_label_ids,
            evidence_refs=candidate.evidence_refs,
            source_hashes=candidate.source_hashes,
            supported_kinds=candidate.supported_kinds,
            excluded_cheaper_kinds=candidate.excluded_cheaper_kinds,
            trigger_contract=candidate.trigger_contract,
            compiled_payload=candidate.compiled_payload,
            verifier_contract=candidate.verifier_contract,
            negative_transfer_boundary=candidate.negative_transfer_boundary,
            tested_region=candidate.tested_region,
            rollback_action=candidate.rollback_action,
            partition=candidate.partition,
            operating_surface_profile_id=candidate.operating_surface_profile_id,
            tomography_assessment_id=candidate.tomography_assessment_id,
            model_internal_residual=candidate.model_internal_residual,
            decision_id=candidate.decision_id,
        )

    @staticmethod
    def _revalidate_plan(plan: CompilationPlan) -> CompilationPlan:
        if not isinstance(plan, CompilationPlan):
            raise TypeError("plan must be CompilationPlan")
        return CompilationPlan(
            plan_id=plan.plan_id,
            candidate_id=plan.candidate_id,
            selected_kind=plan.selected_kind,
            rejected_cheaper_kinds=plan.rejected_cheaper_kinds,
            evidence_refs=plan.evidence_refs,
            projected_model_calls=plan.projected_model_calls,
            expected_disposition=plan.expected_disposition,
        )

    @staticmethod
    def _same_plan(left: CompilationPlan, right: CompilationPlan) -> bool:
        return (
            left.plan_id == right.plan_id
            and left.candidate_id == right.candidate_id
            and left.selected_kind is right.selected_kind
            and dict(left.rejected_cheaper_kinds) == dict(right.rejected_cheaper_kinds)
            and tuple(left.evidence_refs) == tuple(right.evidence_refs)
            and left.projected_model_calls == right.projected_model_calls
            and left.expected_disposition is right.expected_disposition
        )

    def compile(
        self,
        candidate: CompilationCandidate,
        plan: CompilationPlan,
    ) -> CompiledCapability:
        validation = self.store.validate()
        if not getattr(validation, "ok", False):
            raise ValueError("compilation store integrity validation failed before compilation")

        candidate = self._revalidate_candidate(candidate)
        plan = self._revalidate_plan(plan)
        if plan.candidate_id != candidate.candidate_id:
            raise ValueError("compilation plan belongs to a different candidate")

        expected_plan = self.planner.plan(candidate)
        if not self._same_plan(plan, expected_plan):
            raise ValueError("compilation plan does not match deterministic cheapest-owner plan")

        self.store.append_candidate(candidate)
        self.store.append_decision(plan)

        existing = tuple(self.store.capabilities())
        same_candidate = [
            item
            for item in existing
            if item.candidate_id == candidate.candidate_id
            and item.selected_kind is plan.selected_kind
        ]
        if same_candidate:
            if len(same_candidate) != 1:
                raise ValueError("candidate has multiple compiled capability records")
            return same_candidate[0]

        # A provisional v1 artifact gives the stable key without consulting mutable state.
        provisional = CompiledCapability.create(
            candidate=candidate,
            selected_kind=plan.selected_kind,
            version=1,
            previous_capability_id=None,
            disposition=plan.expected_disposition,
            handoff=_HANDOFFS[plan.selected_kind],
        )
        prior_versions = [
            item for item in existing if item.capability_key == provisional.capability_key
        ]
        if prior_versions:
            prior_versions.sort(key=lambda item: (item.version, item.capability_id))
            latest = prior_versions[-1]
            expected_versions = list(range(1, latest.version + 1))
            observed_versions = sorted(item.version for item in prior_versions)
            if observed_versions != expected_versions:
                raise ValueError("existing compiled capability version lineage is not contiguous")
            version = latest.version + 1
            previous_capability_id = latest.capability_id
        else:
            version = 1
            previous_capability_id = None

        capability = CompiledCapability.create(
            candidate=candidate,
            selected_kind=plan.selected_kind,
            version=version,
            previous_capability_id=previous_capability_id,
            disposition=plan.expected_disposition,
            handoff=_HANDOFFS[plan.selected_kind],
        )
        self.store.append_capability(capability)
        return capability
