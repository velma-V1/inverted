"""Deterministic zero-call admission for Stage-7 tomography."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .causal_core import DivergenceClass
from .core import Partition
from .tomography_core import TomographyAxis
from .tomography_planner import TomographyPlan, TomographyPlanner


class TomographyEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    ANSWERED_BY_EXISTING_EVIDENCE = "ANSWERED_BY_EXISTING_EVIDENCE"
    NO_DECISION_CHANGING_PROBE = "NO_DECISION_CHANGING_PROBE"
    INSUFFICIENT_REPLAY_STATE = "INSUFFICIENT_REPLAY_STATE"
    PROTECTED_PARTITION = "PROTECTED_PARTITION"
    REQUIRES_PRIOR_LOCALIZATION = "REQUIRES_PRIOR_LOCALIZATION"


_STAGE7_DIVERGENCES = frozenset({
    DivergenceClass.TOOL_CAPABILITY,
    DivergenceClass.TOOL_SELECTION,
    DivergenceClass.TOOL_ARGUMENTS,
    DivergenceClass.TOOL_INTERPRETATION,
    DivergenceClass.VERIFIER_FEEDBACK,
    DivergenceClass.RECOVERY_POLICY,
    DivergenceClass.SKILL_DEFICIT,
    DivergenceClass.MODEL_CAPABILITY_LIMIT,
})
_STAGE7_DECISIONS = frozenset({"D2", "D6", "D7", "D8", "D11", "D12"})


@dataclass(frozen=True)
class TomographyEligibilityResult:
    failure_snapshot_id: str
    status: TomographyEligibilityStatus
    partition: Partition
    divergence: DivergenceClass
    active_decision_ids: tuple[str, ...]
    evidence_sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.failure_snapshot_id, str) or not self.failure_snapshot_id.strip():
            raise ValueError("failure_snapshot_id must be non-empty")
        if not isinstance(self.status, TomographyEligibilityStatus):
            raise TypeError("status must be TomographyEligibilityStatus")
        if not isinstance(self.partition, Partition):
            raise TypeError("partition must be Partition")
        if not isinstance(self.divergence, DivergenceClass):
            raise TypeError("divergence must be DivergenceClass")
        object.__setattr__(self, "active_decision_ids", tuple(self.active_decision_ids))
        object.__setattr__(self, "evidence_sources", tuple(self.evidence_sources))
        if len(set(self.active_decision_ids)) != len(self.active_decision_ids):
            raise ValueError("active_decision_ids must be unique")
        if any(item not in _STAGE7_DECISIONS for item in self.active_decision_ids):
            raise ValueError("active_decision_ids contains a non-Stage-7 decision")
        if len(set(self.evidence_sources)) != len(self.evidence_sources):
            raise ValueError("evidence_sources must be unique")

    @property
    def model_calls(self) -> int:
        return 0


@dataclass(frozen=True)
class TomographyAutoPlanResult:
    eligibility: TomographyEligibilityResult
    plan: TomographyPlan | None

    def __post_init__(self) -> None:
        if not isinstance(self.eligibility, TomographyEligibilityResult):
            raise TypeError("eligibility must be TomographyEligibilityResult")
        if self.plan is not None and not isinstance(self.plan, TomographyPlan):
            raise TypeError("plan must be TomographyPlan or None")
        if self.eligibility.status is not TomographyEligibilityStatus.ELIGIBLE and self.plan is not None:
            raise ValueError("ineligible tomography result cannot carry a plan")
        if self.plan is not None and self.plan.model_calls != 0:
            raise ValueError("Stage-7 auto-plan must remain zero-call")

    @property
    def model_calls(self) -> int:
        return 0


def _bool(name: str, value: bool) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{name} must be boolean")
    return value


def classify_tomography_eligibility(
    *,
    failure_snapshot_id: str,
    partition: Partition,
    divergence: DivergenceClass,
    decision_ids: tuple[str, ...],
    reconstructable_state: bool = True,
    answered_by_existing_evidence: bool = False,
    requires_prior_localization: bool = False,
    stage5_persistent_residual: bool = False,
    stage6_external_boundary: bool = False,
    historical_contrast: bool = False,
) -> TomographyEligibilityResult:
    """Classify whether an observable failure region may enter Stage 7.

    Precedence is conservative: protected evidence is rejected before all other
    logic, then replay reconstructability, existing answers, explicit prior
    localization requirements, decision value, and finally Stage-7 evidence.
    The function is pure and constructs no adapters, clients, transports, or
    model calls.
    """

    if not isinstance(failure_snapshot_id, str) or not failure_snapshot_id.strip():
        raise ValueError("failure_snapshot_id must be non-empty")
    part = partition if isinstance(partition, Partition) else Partition(partition)
    kind = divergence if isinstance(divergence, DivergenceClass) else DivergenceClass(divergence)
    decisions = tuple(decision_ids)
    if any(not isinstance(item, str) or not item.strip() for item in decisions):
        raise ValueError("decision_ids must contain non-empty strings")
    if len(set(decisions)) != len(decisions):
        raise ValueError("decision_ids must be unique")

    reconstructable = _bool("reconstructable_state", reconstructable_state)
    answered = _bool("answered_by_existing_evidence", answered_by_existing_evidence)
    prior = _bool("requires_prior_localization", requires_prior_localization)
    stage5 = _bool("stage5_persistent_residual", stage5_persistent_residual)
    stage6 = _bool("stage6_external_boundary", stage6_external_boundary)
    historical = _bool("historical_contrast", historical_contrast)

    active_decisions = tuple(item for item in decisions if item in _STAGE7_DECISIONS)
    sources: list[str] = []
    if kind in _STAGE7_DIVERGENCES:
        sources.append("autopsy_stage7_divergence")
    if stage5:
        sources.append("stage5_persistent_residual")
    if stage6:
        sources.append("stage6_external_boundary")
    if historical:
        sources.append("historical_reconstructable_contrast")

    if part in {Partition.FRESH, Partition.SEALED}:
        status = TomographyEligibilityStatus.PROTECTED_PARTITION
    elif not reconstructable:
        status = TomographyEligibilityStatus.INSUFFICIENT_REPLAY_STATE
    elif answered:
        status = TomographyEligibilityStatus.ANSWERED_BY_EXISTING_EVIDENCE
    elif prior:
        status = TomographyEligibilityStatus.REQUIRES_PRIOR_LOCALIZATION
    elif not active_decisions:
        status = TomographyEligibilityStatus.NO_DECISION_CHANGING_PROBE
    elif sources:
        status = TomographyEligibilityStatus.ELIGIBLE
    else:
        status = TomographyEligibilityStatus.REQUIRES_PRIOR_LOCALIZATION

    return TomographyEligibilityResult(
        failure_snapshot_id=failure_snapshot_id,
        status=status,
        partition=part,
        divergence=kind,
        active_decision_ids=active_decisions,
        evidence_sources=tuple(sources),
    )


def plan_eligible_tomography(
    *,
    failure_snapshot_id: str,
    parent_state_hash: str,
    partition: Partition,
    divergence: DivergenceClass,
    decision_ids: tuple[str, ...],
    baseline_evidence_refs: tuple[str, ...],
    intervention_ids: Mapping[TomographyAxis, str],
    changed_dimensions: Mapping[TomographyAxis, tuple[str, ...]],
    reconstructable_state: bool = True,
    answered_by_existing_evidence: bool = False,
    requires_prior_localization: bool = False,
    stage5_persistent_residual: bool = False,
    stage6_external_boundary: bool = False,
    historical_contrast: bool = False,
    resolved_axes: tuple[TomographyAxis, ...] = (),
    max_new_probes: int = 3,
    extension_authorized: bool = False,
    external_supports_exhausted: bool = False,
    deterministic_scoring: bool = True,
    baseline_linked: bool = True,
    parent_state_resolves: bool = True,
    protected_direct_solved_veto: bool = False,
) -> TomographyAutoPlanResult:
    """Classify and, only when eligible, delegate to the canonical Stage-7 planner."""

    eligibility = classify_tomography_eligibility(
        failure_snapshot_id=failure_snapshot_id,
        partition=partition,
        divergence=divergence,
        decision_ids=decision_ids,
        reconstructable_state=reconstructable_state,
        answered_by_existing_evidence=answered_by_existing_evidence,
        requires_prior_localization=requires_prior_localization,
        stage5_persistent_residual=stage5_persistent_residual,
        stage6_external_boundary=stage6_external_boundary,
        historical_contrast=historical_contrast,
    )
    if eligibility.status is not TomographyEligibilityStatus.ELIGIBLE:
        return TomographyAutoPlanResult(eligibility=eligibility, plan=None)

    plan = TomographyPlanner().plan(
        failure_snapshot_id=failure_snapshot_id,
        parent_state_hash=parent_state_hash,
        partition=partition,
        divergence=divergence,
        decision_ids=eligibility.active_decision_ids,
        baseline_evidence_refs=tuple(baseline_evidence_refs),
        intervention_ids=intervention_ids,
        changed_dimensions=changed_dimensions,
        resolved_axes=resolved_axes,
        max_new_probes=max_new_probes,
        extension_authorized=extension_authorized,
        external_supports_exhausted=external_supports_exhausted,
        deterministic_scoring=deterministic_scoring,
        baseline_linked=baseline_linked,
        parent_state_resolves=parent_state_resolves,
        protected_direct_solved_veto=protected_direct_solved_veto,
        protected_partition_authorized=False,
    )
    return TomographyAutoPlanResult(eligibility=eligibility, plan=plan)
