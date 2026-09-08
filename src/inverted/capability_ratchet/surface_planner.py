"""Adaptive one-axis planning for V3 Stage-5 operating surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any

from inverted.universal_tuning.statistics import (
    NONINFERIORITY_MARGIN,
    SUPERIORITY_MARGIN,
)

from .causal_core import (
    CausalHypothesis,
    InterventionDefinition,
    InterventionKind,
)
from .core import MechanismLabel
from .surface_core import (
    OperatingSurfaceProfile,
    SurfaceAxis,
    SurfaceDisposition,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfacePoint,
    SurfaceStudy,
)


@dataclass(frozen=True)
class SurfacePlan:
    points: tuple[SurfacePoint, ...]
    decision_reason: str
    minimum_physical_calls: int
    expected_physical_calls: int
    worst_case_physical_calls: int
    protected_exploration_calls: int
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        if not isinstance(self.decision_reason, str) or not self.decision_reason.strip():
            raise ValueError("decision_reason is required")
        values = (
            self.minimum_physical_calls,
            self.expected_physical_calls,
            self.worst_case_physical_calls,
            self.protected_exploration_calls,
        )
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            for value in values
        ):
            raise ValueError("surface plan call counts must be non-negative integers")
        if not self.minimum_physical_calls <= self.expected_physical_calls <= self.worst_case_physical_calls:
            raise ValueError("surface plan call counts must be ordered")
        if self.protected_exploration_calls > self.worst_case_physical_calls:
            raise ValueError("protected exploration calls cannot exceed worst-case calls")
        ids = tuple(point.surface_point_id for point in self.points)
        if len(set(ids)) != len(ids):
            raise ValueError("surface plan points must be unique")
        if self.stop_reason is not None and self.points:
            raise ValueError("stopped surface plans cannot contain executable points")


class SurfacePlanner:
    """Select only the next decision-changing Stage-5 probes."""

    superiority_margin = SUPERIORITY_MARGIN
    noninferiority_margin = NONINFERIORITY_MARGIN

    def __init__(self, surface_store: Any, evidence_compiler: Any) -> None:
        if not hasattr(surface_store, "observations") or not hasattr(surface_store, "profiles"):
            raise TypeError("surface_store must expose observations() and profiles()")
        if not hasattr(evidence_compiler, "answered_points"):
            raise TypeError("evidence_compiler must expose answered_points()")
        self.surface_store = surface_store
        self.evidence_compiler = evidence_compiler

    @staticmethod
    def eligible_axes(
        mechanism: MechanismLabel,
        hypothesis: CausalHypothesis,
        intervention: InterventionDefinition,
        *,
        cognition_relevant: bool = False,
    ) -> tuple[SurfaceAxis, ...]:
        if not isinstance(mechanism, MechanismLabel):
            raise TypeError("mechanism must be MechanismLabel")
        if not isinstance(hypothesis, CausalHypothesis):
            raise TypeError("hypothesis must be CausalHypothesis")
        if not isinstance(intervention, InterventionDefinition):
            raise TypeError("intervention must be InterventionDefinition")
        if mechanism.hypothesis_id != hypothesis.hypothesis_id:
            raise ValueError("mechanism and hypothesis lineage differ")
        if intervention.hypothesis_id != hypothesis.hypothesis_id:
            raise ValueError("intervention and hypothesis lineage differ")

        if intervention.kind is InterventionKind.COGNITION:
            axes = [SurfaceAxis.REASONING_BUDGET]
            if cognition_relevant:
                axes.append(SurfaceAxis.TEMPERATURE)
            return tuple(axes)
        if intervention.kind is InterventionKind.CONTEXT:
            return (
                SurfaceAxis.CONTEXT_DOSE,
                SurfaceAxis.CONTEXT_POSITION,
                SurfaceAxis.DELIVERY_MODE,
            )
        if intervention.kind is InterventionKind.REPRESENTATION:
            return (
                SurfaceAxis.REPRESENTATION,
                SurfaceAxis.ORDER,
                SurfaceAxis.PLACEMENT,
            )
        if intervention.kind is InterventionKind.DELIVERY:
            return (
                SurfaceAxis.TIMING,
                SurfaceAxis.RECURRENCE,
                SurfaceAxis.TRIGGER_MODE,
            )
        return ()

    @staticmethod
    def _success(observation: SurfaceObservation) -> bool:
        if observation.evidence_kind is not SurfaceEvidenceKind.SAME_STATE_CAUSAL:
            return False
        metrics = observation.metrics
        return bool(
            metrics.get("completed")
            and metrics.get("semantic_pass")
            and metrics.get("contract_pass")
            and not metrics.get("failure_classes")
        )

    def _point_cost(self, study: SurfaceStudy, axis: SurfaceAxis, value: Any) -> int:
        estimator = getattr(self.evidence_compiler, "point_physical_calls", None)
        if callable(estimator):
            cost = estimator(study, self._point(study, axis, value))
            if not isinstance(cost, int) or isinstance(cost, bool) or cost < 1:
                raise ValueError("surface point physical-call estimate must be a positive integer")
            return cost
        # Compatibility fallback for isolated planner test doubles. Production
        # planning always uses the frozen fixture estimator above.
        if axis is SurfaceAxis.REASONING_BUDGET:
            return 1 if value == 0 else 2
        if axis is SurfaceAxis.TEMPERATURE:
            return 2
        return 1

    @staticmethod
    def _is_numeric(values: tuple[Any, ...]) -> bool:
        return all(isinstance(value, Real) and not isinstance(value, bool) for value in values)

    def _resolved_profile(
        self, study: SurfaceStudy, axis: SurfaceAxis
    ) -> OperatingSurfaceProfile | None:
        profiles = tuple(self.surface_store.profiles(study.mechanism_id))
        matches = [
            profile
            for profile in profiles
            if isinstance(profile, OperatingSurfaceProfile)
            and profile.study_id == study.study_id
            and profile.axis is axis
            and profile.disposition is not SurfaceDisposition.UNRESOLVED
            and not profile.unresolved_edges
        ]
        return matches[-1] if matches else None

    def _same_state_rows(
        self, study: SurfaceStudy, axis: SurfaceAxis
    ) -> tuple[SurfaceObservation, ...]:
        return tuple(
            row
            for row in self.surface_store.observations(study.study_id)
            if isinstance(row, SurfaceObservation)
            and row.axis is axis
            and row.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL
        )

    @staticmethod
    def _point(
        study: SurfaceStudy,
        axis: SurfaceAxis,
        value: Any,
        *,
        protected: bool = False,
    ) -> SurfacePoint:
        return SurfacePoint.create(
            study=study,
            axis=axis,
            value=value,
            decision_id=study.decision_id,
            protected_exploration=protected,
        )

    def _ordered_candidates(
        self,
        study: SurfaceStudy,
        axis: SurfaceAxis,
        unresolved_values: tuple[Any, ...],
    ) -> tuple[SurfacePoint, ...]:
        if not unresolved_values:
            return ()
        rows = self._same_state_rows(study, axis)
        successful = tuple(row.value for row in rows if self._success(row))

        if not self._is_numeric(tuple(study.axis_values[axis.value])):
            first = unresolved_values[0]
            if len(unresolved_values) == 1:
                return (self._point(study, axis, first),)
            extreme = unresolved_values[-1]
            return (
                self._point(study, axis, first),
                self._point(study, axis, extreme, protected=True),
            )

        ordered = tuple(sorted(unresolved_values))
        chosen: list[SurfacePoint] = []
        if successful:
            lower_success = min(successful)
            lower = tuple(value for value in ordered if value < lower_success)
            if lower:
                chosen.append(self._point(study, axis, lower[0]))
            upper_success = max(successful)
            upper = tuple(value for value in ordered if value > upper_success)
            if upper:
                chosen.append(self._point(study, axis, upper[-1], protected=True))
        else:
            chosen.append(self._point(study, axis, ordered[0]))
            if len(ordered) > 1:
                chosen.append(self._point(study, axis, ordered[-1], protected=True))

        represented = {point.value for point in chosen}
        for value in ordered:
            if value not in represented:
                chosen.append(self._point(study, axis, value))
        return tuple(chosen)

    def plan_next(self, study: SurfaceStudy, *, max_new_points: int = 2) -> SurfacePlan:
        if not isinstance(study, SurfaceStudy):
            raise TypeError("study must be SurfaceStudy")
        if (
            not isinstance(max_new_points, int)
            or isinstance(max_new_points, bool)
            or max_new_points < 1
        ):
            raise ValueError("max_new_points must be a positive integer")
        answered = frozenset(self.evidence_compiler.answered_points(study))
        resolved: list[OperatingSurfaceProfile] = []

        for axis in study.axes:
            profile = self._resolved_profile(study, axis)
            if profile is not None:
                resolved.append(profile)
                continue

            values = tuple(study.axis_values[axis.value])
            unresolved_values = tuple(
                value
                for value in values
                if self._point(study, axis, value).surface_point_id not in answered
            )
            if not unresolved_values:
                continue

            candidates = self._ordered_candidates(study, axis, unresolved_values)
            selected = candidates[:max_new_points]
            protected = tuple(
                point for point in candidates if point.protected_exploration
            )
            reserve = (
                self._point_cost(study, axis, protected[0].value) if protected else 0
            )
            selected_cost = sum(
                self._point_cost(study, axis, point.value) for point in selected
            )
            protected_selected = any(
                point.protected_exploration for point in selected
            )
            expected = selected_cost if protected_selected else selected_cost + reserve
            worst = sum(
                self._point_cost(study, axis, value) for value in unresolved_values
            )
            expected = min(expected, worst)
            reason = (
                f"adaptively bracket {axis.value}: probe the lowest unresolved boundary "
                "and preserve a protected extreme capable of revealing saturation or harm"
            )
            return SurfacePlan(
                points=tuple(selected),
                decision_reason=reason,
                minimum_physical_calls=selected_cost,
                expected_physical_calls=expected,
                worst_case_physical_calls=worst,
                protected_exploration_calls=reserve,
            )

        if len(resolved) == len(study.axes) and resolved:
            disposition = (
                resolved[0].disposition.value if len(resolved) == 1 else "ALL_AXES"
            )
            return SurfacePlan(
                points=(),
                decision_reason=(
                    "stored operating-surface evidence already settles the active decision"
                ),
                minimum_physical_calls=0,
                expected_physical_calls=0,
                worst_case_physical_calls=0,
                protected_exploration_calls=0,
                stop_reason=f"surface already resolved as {disposition}",
            )
        return SurfacePlan(
            points=(),
            decision_reason=(
                "stored same-state evidence leaves no unresolved registered point"
            ),
            minimum_physical_calls=0,
            expected_physical_calls=0,
            worst_case_physical_calls=0,
            protected_exploration_calls=0,
            stop_reason="all registered surface points are already answered",
        )
