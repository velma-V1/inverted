"""Minimum decision-changing tournament geometry for V3 causal replay research."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .causal_core import (
    CausalHypothesis,
    HypothesisStatus,
    InterventionDefinition,
    InterventionKind,
)
from .causal_store import CausalEvidenceStore
from .core import FailureFixture


def _branch_id(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return f"branch-{hashlib.sha256(encoded).hexdigest()[:24]}"


@dataclass(frozen=True)
class TournamentBranch:
    branch_id: str
    intervention_ids: tuple[str, ...]
    mode: str
    decision_reason: str
    protected_exploration: bool
    projected_physical_calls: int
    hypothesis_id: str | None = None
    unresolved_decision: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.branch_id, str) or not self.branch_id:
            raise ValueError("branch_id is required")
        ids = tuple(self.intervention_ids)
        if any(not isinstance(item, str) or not item for item in ids):
            raise ValueError("intervention_ids must contain non-blank strings")
        object.__setattr__(self, "intervention_ids", ids)
        if self.mode not in {"EXACT", "TARGET", "SHAM", "DETERMINISTIC"}:
            raise ValueError("unsupported tournament branch mode")
        if not isinstance(self.decision_reason, str) or not self.decision_reason.strip():
            raise ValueError("decision_reason is required")
        if not isinstance(self.unresolved_decision, str) or not self.unresolved_decision.strip():
            raise ValueError("unresolved_decision is required")
        if type(self.protected_exploration) is not bool:
            raise TypeError("protected_exploration must be boolean")
        if (
            not isinstance(self.projected_physical_calls, int)
            or isinstance(self.projected_physical_calls, bool)
            or self.projected_physical_calls < 0
        ):
            raise ValueError("projected_physical_calls must be a non-negative integer")


@dataclass(frozen=True)
class TournamentPlan:
    failure_snapshot_id: str
    branches: tuple[TournamentBranch, ...]
    rejected_hypothesis_ids: tuple[str, ...]
    minimum_physical_calls: int
    expected_physical_calls: int
    worst_case_physical_calls: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "branches", tuple(self.branches))
        object.__setattr__(self, "rejected_hypothesis_ids", tuple(self.rejected_hypothesis_ids))
        if not self.failure_snapshot_id:
            raise ValueError("failure_snapshot_id is required")
        geometry = (
            self.minimum_physical_calls,
            self.expected_physical_calls,
            self.worst_case_physical_calls,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in geometry):
            raise ValueError("tournament call geometry must contain non-negative integers")
        if not geometry[0] <= geometry[1] <= geometry[2]:
            raise ValueError("tournament call geometry must be monotonic")


def _decision_changing(hypothesis: CausalHypothesis) -> bool:
    if hypothesis.status not in {HypothesisStatus.ACTIVE, HypothesisStatus.UNRESOLVED}:
        return False
    expected = " ".join(hypothesis.expected_if_true.split()).casefold()
    falsifier = " ".join(hypothesis.falsifier.split()).casefold()
    return expected != falsifier


def _target_mode(intervention: InterventionDefinition) -> str:
    if intervention.projected_physical_calls == 0 or intervention.kind is InterventionKind.DETERMINISTIC:
        return "DETERMINISTIC"
    return "TARGET"


def _branch_for_target(
    hypothesis: CausalHypothesis,
    intervention: InterventionDefinition,
) -> TournamentBranch:
    ids = intervention.composition or (intervention.intervention_id,)
    mode = _target_mode(intervention)
    decision = f"resolve hypothesis {hypothesis.hypothesis_id}: {hypothesis.claim}"
    payload = {
        "mode": mode,
        "hypothesis_id": hypothesis.hypothesis_id,
        "intervention_ids": list(ids),
        "failure_snapshot_id": hypothesis.failure_snapshot_id,
        "parent_state_hash": hypothesis.parent_state_hash,
    }
    return TournamentBranch(
        branch_id=_branch_id(payload),
        intervention_ids=ids,
        mode=mode,
        decision_reason=(
            f"test whether {intervention.label} changes the unresolved causal decision"
        ),
        protected_exploration=(
            hypothesis.protected_exploration or intervention.protected_exploration
        ),
        projected_physical_calls=intervention.projected_physical_calls,
        hypothesis_id=hypothesis.hypothesis_id,
        unresolved_decision=decision,
    )


def _branch_for_sham(
    hypothesis: CausalHypothesis,
    sham: InterventionDefinition,
) -> TournamentBranch:
    decision = f"falsify causal attribution for hypothesis {hypothesis.hypothesis_id}"
    payload = {
        "mode": "SHAM",
        "hypothesis_id": hypothesis.hypothesis_id,
        "intervention_ids": [sham.intervention_id],
        "failure_snapshot_id": hypothesis.failure_snapshot_id,
        "parent_state_hash": hypothesis.parent_state_hash,
    }
    return TournamentBranch(
        branch_id=_branch_id(payload),
        intervention_ids=(sham.intervention_id,),
        mode="SHAM",
        decision_reason="matched control can distinguish treatment effect from nonspecific replay change",
        protected_exploration=(
            hypothesis.protected_exploration or sham.protected_exploration
        ),
        projected_physical_calls=sham.projected_physical_calls,
        hypothesis_id=hypothesis.hypothesis_id,
        unresolved_decision=decision,
    )


def _exact_branch(fixture: FailureFixture) -> TournamentBranch:
    payload = {
        "mode": "EXACT",
        "failure_snapshot_id": fixture.failure_snapshot_id,
        "parent_state_hash": fixture.state_hash,
    }
    return TournamentBranch(
        branch_id=_branch_id(payload),
        intervention_ids=(),
        mode="EXACT",
        decision_reason="measure reproducibility before interpreting intervention deltas",
        protected_exploration=False,
        projected_physical_calls=1,
        hypothesis_id=None,
        unresolved_decision="determine whether the parent failure is reproducible above local noise",
    )


def _select_with_protection(
    candidates: list[TournamentBranch], capacity: int
) -> list[TournamentBranch]:
    if capacity <= 0 or not candidates:
        return []
    if len(candidates) <= capacity:
        return list(candidates)
    protected = [item for item in candidates if item.protected_exploration]
    ordinary = [item for item in candidates if not item.protected_exploration]
    selected: list[TournamentBranch] = []
    if protected:
        selected.append(protected[0])
    for item in candidates:
        if item in selected:
            continue
        if len(selected) >= capacity:
            break
        selected.append(item)
    if not selected and ordinary:
        selected.append(ordinary[0])
    return selected


class TournamentPlanner:
    """Select the smallest branch set that can change current causal decisions."""

    def __init__(self, causal_store: CausalEvidenceStore) -> None:
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.causal_store = causal_store

    def plan(
        self,
        fixture: FailureFixture,
        hypotheses: Iterable[CausalHypothesis],
        interventions: Iterable[InterventionDefinition],
        *,
        reproducibility_known: bool = True,
        max_branches: int = 8,
    ) -> TournamentPlan:
        if not isinstance(fixture, FailureFixture):
            raise TypeError("fixture must be FailureFixture")
        if not isinstance(max_branches, int) or isinstance(max_branches, bool) or max_branches < 1:
            raise ValueError("max_branches must be a positive integer")
        if type(reproducibility_known) is not bool:
            raise TypeError("reproducibility_known must be boolean")
        validation = self.causal_store.validate()
        if not validation.ok:
            raise ValueError("causal evidence store integrity validation failed")

        supplied_hypotheses = tuple(hypotheses)
        supplied_interventions = tuple(interventions)
        registered_hypotheses = {
            item.hypothesis_id: item
            for item in self.causal_store.hypotheses(fixture.failure_snapshot_id)
        }
        for hypothesis in supplied_hypotheses:
            if not isinstance(hypothesis, CausalHypothesis):
                raise TypeError("hypotheses must contain CausalHypothesis values")
            if hypothesis.failure_snapshot_id != fixture.failure_snapshot_id:
                raise ValueError("tournament hypothesis failure lineage mismatch")
            if hypothesis.parent_state_hash != fixture.state_hash:
                raise ValueError("tournament hypothesis parent state mismatch")
            if registered_hypotheses.get(hypothesis.hypothesis_id) != hypothesis:
                raise ValueError("tournament hypothesis is not registered")
        for intervention in supplied_interventions:
            if not isinstance(intervention, InterventionDefinition):
                raise TypeError("interventions must contain InterventionDefinition values")
            if intervention.failure_snapshot_id != fixture.failure_snapshot_id:
                raise ValueError("tournament intervention failure lineage mismatch")
            if intervention.parent_state_hash != fixture.state_hash:
                raise ValueError("tournament intervention parent state mismatch")
            if self.causal_store.get_intervention(intervention.intervention_id) != intervention:
                raise ValueError("tournament intervention is not registered")

        by_hypothesis: dict[str, list[InterventionDefinition]] = {}
        for intervention in supplied_interventions:
            by_hypothesis.setdefault(intervention.hypothesis_id, []).append(intervention)

        target_candidates: list[TournamentBranch] = []
        sham_by_hypothesis: dict[str, list[TournamentBranch]] = {}
        rejected: list[str] = []
        selected_target_ids: dict[str, str] = {}

        for hypothesis in supplied_hypotheses:
            if not _decision_changing(hypothesis):
                rejected.append(hypothesis.hypothesis_id)
                continue
            options = by_hypothesis.get(hypothesis.hypothesis_id, [])
            targets = [
                item for item in options
                if item.kind not in {InterventionKind.SHAM, InterventionKind.ABLATION}
            ]
            if not targets:
                rejected.append(hypothesis.hypothesis_id)
                continue
            targets.sort(
                key=lambda item: (
                    not item.protected_exploration,
                    item.projected_physical_calls,
                    item.intervention_id,
                )
            )
            target = targets[0]
            selected_target_ids[hypothesis.hypothesis_id] = target.intervention_id
            target_candidates.append(_branch_for_target(hypothesis, target))
            shams = [
                item for item in options
                if item.kind is InterventionKind.SHAM and item.sham_for == target.intervention_id
            ]
            sham_by_hypothesis[hypothesis.hypothesis_id] = [
                _branch_for_sham(hypothesis, item)
                for item in sorted(shams, key=lambda value: value.intervention_id)
            ]

        branches: list[TournamentBranch] = []
        if not reproducibility_known:
            branches.append(_exact_branch(fixture))

        remaining = max_branches - len(branches)
        selected_targets = _select_with_protection(target_candidates, remaining)
        branches.extend(selected_targets)
        remaining = max_branches - len(branches)

        # Matched controls come only after each live hypothesis has had a chance to
        # receive one targeted branch; this prevents cheap duplicate controls from
        # displacing a decision-changing treatment.
        if remaining > 0:
            selected_hypothesis_ids = [
                branch.hypothesis_id for branch in selected_targets if branch.hypothesis_id
            ]
            sham_candidates: list[TournamentBranch] = []
            for hypothesis_id in selected_hypothesis_ids:
                sham_candidates.extend(sham_by_hypothesis.get(hypothesis_id, [])[:1])
            branches.extend(_select_with_protection(sham_candidates, remaining))

        worst = sum(branch.projected_physical_calls for branch in branches)
        minimum = sum(
            branch.projected_physical_calls
            for branch in branches
            if branch.mode in {"EXACT", "TARGET", "DETERMINISTIC"}
        )
        expected = worst
        return TournamentPlan(
            failure_snapshot_id=fixture.failure_snapshot_id,
            branches=tuple(branches),
            rejected_hypothesis_ids=tuple(rejected),
            minimum_physical_calls=minimum,
            expected_physical_calls=expected,
            worst_case_physical_calls=worst,
        )


def build_ablations(
    successful_compound: InterventionDefinition,
    component_ids: Iterable[str],
) -> tuple[InterventionDefinition, ...]:
    """Build leave-one-mechanism-out geometry plus one matched compound sham.

    This function records causal geometry only. Later orchestration resolves the
    component IDs into executable registered treatments; it deliberately does not
    fabricate model-visible payload bytes here.
    """

    if not isinstance(successful_compound, InterventionDefinition):
        raise TypeError("successful_compound must be InterventionDefinition")
    components = tuple(component_ids)
    if len(components) < 2 or any(not isinstance(item, str) or not item for item in components):
        raise ValueError("compound ablation requires at least two non-blank component IDs")
    unique_components = tuple(dict.fromkeys(components))
    if len(unique_components) < 2:
        raise ValueError("compound ablation requires at least two distinct mechanisms")

    generated: list[InterventionDefinition] = []
    for component in unique_components:
        remainder = tuple(item for item in components if item != component)
        generated.append(InterventionDefinition.create(
            hypothesis_id=successful_compound.hypothesis_id,
            failure_snapshot_id=successful_compound.failure_snapshot_id,
            parent_state_hash=successful_compound.parent_state_hash,
            kind=InterventionKind.ABLATION,
            label=f"{successful_compound.label} without {component}",
            changed_dimensions=(),
            overrides={},
            expected_causal_implication=(
                f"if {component} is causally required, removing it should reduce the compound repair"
            ),
            projected_physical_calls=successful_compound.projected_physical_calls,
            composition=remainder,
            ablates=(component,),
            protected_exploration=successful_compound.protected_exploration,
        ))

    generated.append(InterventionDefinition.create(
        hypothesis_id=successful_compound.hypothesis_id,
        failure_snapshot_id=successful_compound.failure_snapshot_id,
        parent_state_hash=successful_compound.parent_state_hash,
        kind=InterventionKind.SHAM,
        label=f"matched sham for {successful_compound.label}",
        changed_dimensions=(),
        overrides={},
        expected_causal_implication=(
            "a matched compound control should not reproduce the targeted mechanism gain"
        ),
        projected_physical_calls=successful_compound.projected_physical_calls,
        composition=components,
        sham_for=successful_compound.intervention_id,
        protected_exploration=successful_compound.protected_exploration,
    ))
    return tuple(generated)
