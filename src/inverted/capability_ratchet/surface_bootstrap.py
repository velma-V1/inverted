"""Zero-call bootstrap from canonical MOVEMENT evidence into Stage-5 studies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .causal_core import InterventionDefinition, InterventionKind
from .core import MechanismLabel, PromotionEvent, PromotionState
from .historical import V2EvidenceSource
from .surface_core import SurfaceAxis, SurfaceEvidenceKind, SurfacePoint, SurfaceStudy
from .surface_lab import OperatingSurfaceLab
from .surface_planner import SurfacePlan


_DEFAULT_AXIS_VALUES = {
    SurfaceAxis.REASONING_BUDGET: (0, 256, 512, 1024, 2048, 4096, 8192),
    SurfaceAxis.CONTEXT_DOSE: (0.25, 0.5, 1.0, 2.0, 4.0),
    SurfaceAxis.REPRESENTATION: (
        "PROSE",
        "TYPED_FIELDS",
        "ORDERED_LIST",
        "LEDGER",
        "DECISION_TABLE",
        "DEPENDENCY_MATRIX",
        "GRAPH",
        "COMPACT_SUMMARY",
        "EXPLICIT_ALTERNATIVES",
    ),
    SurfaceAxis.RECURRENCE: (1, 2, 3),
}

_KIND_AXIS = {
    InterventionKind.COGNITION: SurfaceAxis.REASONING_BUDGET,
    InterventionKind.CONTEXT: SurfaceAxis.CONTEXT_DOSE,
    InterventionKind.REPRESENTATION: SurfaceAxis.REPRESENTATION,
    InterventionKind.DELIVERY: SurfaceAxis.RECURRENCE,
}

_KIND_DECISION = {
    InterventionKind.COGNITION: "D3",
    InterventionKind.CONTEXT: "D5",
    InterventionKind.REPRESENTATION: "D5",
    InterventionKind.DELIVERY: "D5",
}


@dataclass(frozen=True)
class SurfaceBootstrapPlan:
    study: SurfaceStudy
    reused_points: tuple[SurfacePoint, ...]
    unresolved_points: tuple[SurfacePoint, ...]
    historical_prior_count: int
    plan: SurfacePlan

    def __post_init__(self) -> None:
        object.__setattr__(self, "reused_points", tuple(self.reused_points))
        object.__setattr__(self, "unresolved_points", tuple(self.unresolved_points))
        if not isinstance(self.historical_prior_count, int) or isinstance(
            self.historical_prior_count, bool
        ) or self.historical_prior_count < 0:
            raise ValueError("historical_prior_count must be a non-negative integer")


def _movement_keys(lab: OperatingSurfaceLab) -> tuple[tuple[str, str], ...]:
    keys: set[tuple[str, str]] = set()
    for record in lab.replay_store.records():
        if (
            isinstance(record, PromotionEvent)
            and record.to_state is PromotionState.MOVEMENT
        ):
            keys.add((record.failure_snapshot_id, record.mechanism_id))
    return tuple(sorted(keys))


def _matching_labels(
    lab: OperatingSurfaceLab, failure_snapshot_id: str, mechanism_id: str
) -> tuple[MechanismLabel, ...]:
    return tuple(
        record
        for record in lab.replay_store.records()
        if isinstance(record, MechanismLabel)
        and record.failure_snapshot_id == failure_snapshot_id
        and record.mechanism_id == mechanism_id
    )


def _registered_interventions(
    lab: OperatingSurfaceLab, labels: Iterable[MechanismLabel]
) -> tuple[InterventionDefinition, ...]:
    rows: list[InterventionDefinition] = []
    seen: set[str] = set()
    for label in labels:
        for intervention_id in label.intervention_ids:
            if intervention_id in seen:
                continue
            try:
                intervention = lab.causal_store.get_intervention(intervention_id)
            except (KeyError, ValueError):
                continue
            seen.add(intervention_id)
            rows.append(intervention)
    return tuple(rows)


def _budget_from_intervention(intervention: InterventionDefinition) -> int | None:
    for path in intervention.changed_dimensions:
        if path not in intervention.overrides:
            continue
        lowered = path.lower()
        if not (
            lowered.endswith("thinking_budget")
            or lowered.endswith("options.num_predict")
        ):
            continue
        value = intervention.overrides[path]
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _axis_values(
    axis: SurfaceAxis, intervention: InterventionDefinition
) -> tuple[object, ...]:
    values = list(_DEFAULT_AXIS_VALUES[axis])
    if axis is SurfaceAxis.REASONING_BUDGET:
        budget = _budget_from_intervention(intervention)
        if budget is not None and budget not in values:
            values.append(budget)
            values.sort()
    return tuple(values)


def _existing_study(
    lab: OperatingSurfaceLab,
    *,
    failure_snapshot_id: str,
    mechanism_id: str,
    parent_state_hash: str,
) -> SurfaceStudy | None:
    matches = tuple(
        study
        for study in lab.surface_store.studies(mechanism_id)
        if study.failure_snapshot_id == failure_snapshot_id
        and study.parent_state_hash == parent_state_hash
        and study.promotion_state is PromotionState.MOVEMENT
    )
    return matches[-1] if matches else None


def _materialize_initial_study(
    lab: OperatingSurfaceLab,
    failure_snapshot_id: str,
    mechanism_id: str,
) -> SurfaceStudy | None:
    fixture = lab.replay_store.get_failure(failure_snapshot_id)
    if fixture.partition.value in {"FRESH", "SEALED"}:
        return None
    labels = _matching_labels(lab, failure_snapshot_id, mechanism_id)
    if not labels:
        return None

    existing = _existing_study(
        lab,
        failure_snapshot_id=failure_snapshot_id,
        mechanism_id=mechanism_id,
        parent_state_hash=fixture.state_hash,
    )
    if existing is not None:
        return existing

    for intervention in _registered_interventions(lab, reversed(labels)):
        axis = _KIND_AXIS.get(intervention.kind)
        if axis is None:
            continue
        study = SurfaceStudy.create(
            failure_snapshot_id=failure_snapshot_id,
            mechanism_id=mechanism_id,
            parent_state_hash=fixture.state_hash,
            partition=fixture.partition,
            promotion_state=PromotionState.MOVEMENT,
            decision_id=_KIND_DECISION[intervention.kind],
            axes=(axis,),
            axis_values={axis.value: _axis_values(axis, intervention)},
        )
        lab.surface_store.append_study(study)
        return study
    return None


def _point_from_observation(study: SurfaceStudy, row) -> SurfacePoint:
    return SurfacePoint.create(
        study=study,
        axis=row.axis,
        value=row.value,
        decision_id=row.decision_id,
        protected_exploration=row.protected_exploration,
    )


def _unique_points(points: Iterable[SurfacePoint]) -> tuple[SurfacePoint, ...]:
    by_id = {point.surface_point_id: point for point in points}
    return tuple(
        sorted(by_id.values(), key=lambda point: (point.axis.value, repr(point.value)))
    )


def plan_eligible_surfaces(
    lab: OperatingSurfaceLab,
    *,
    source: V2EvidenceSource | None = None,
    max_new_points: int = 2,
) -> tuple[SurfaceBootstrapPlan, ...]:
    """Discover durable MOVEMENT mechanisms and build zero-call Stage-5 plans.

    This function never constructs replay adapters and never executes a replay. It
    may only materialize deterministic Stage-5 metadata derived from canonical
    replay/causal evidence and optional V2 historical priors.
    """
    if not isinstance(lab, OperatingSurfaceLab):
        raise TypeError("lab must be OperatingSurfaceLab")
    if source is not None and not isinstance(source, V2EvidenceSource):
        raise TypeError("source must be V2EvidenceSource")

    plans: list[SurfaceBootstrapPlan] = []
    for failure_snapshot_id, mechanism_id in _movement_keys(lab):
        study = _materialize_initial_study(lab, failure_snapshot_id, mechanism_id)
        if study is None:
            continue

        lab.evidence_compiler.same_state_observations(study)
        priors = (
            lab.evidence_compiler.compile_v2_priors(source, study)
            if source is not None
            else ()
        )
        same_state = tuple(
            row
            for row in lab.surface_store.observations(study.study_id)
            if row.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL
        )
        reused = _unique_points(
            _point_from_observation(study, row) for row in same_state
        )
        reused_ids = {point.surface_point_id for point in reused}
        unresolved = _unique_points(
            SurfacePoint.create(
                study=study,
                axis=axis,
                value=value,
                decision_id=study.decision_id,
            )
            for axis in study.axes
            for value in study.axis_values[axis.value]
            if SurfacePoint.create(
                study=study,
                axis=axis,
                value=value,
                decision_id=study.decision_id,
            ).surface_point_id not in reused_ids
        )
        plan = lab.prepare(study.study_id, max_new_points=max_new_points)
        plans.append(
            SurfaceBootstrapPlan(
                study=study,
                reused_points=reused,
                unresolved_points=unresolved,
                historical_prior_count=len(priors),
                plan=plan,
            )
        )
    return tuple(plans)
