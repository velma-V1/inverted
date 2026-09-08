from __future__ import annotations

from dataclasses import dataclass

from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    InterventionDefinition,
    InterventionKind,
    MechanismRole,
)
from inverted.capability_ratchet.core import MechanismLabel, Partition, PromotionState
from inverted.capability_ratchet.surface_core import (
    OperatingSurfaceProfile,
    SurfaceAxis,
    SurfaceBand,
    SurfaceCallGeometry,
    SurfaceDisposition,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfacePoint,
    SurfaceStudy,
)
from inverted.capability_ratchet.surface_planner import SurfacePlanner


STATE = "a" * 64


def study(*, axes=(SurfaceAxis.REASONING_BUDGET,), values=None) -> SurfaceStudy:
    if values is None:
        values = {"REASONING_BUDGET": (0, 256, 512, 1024, 2048, 4096, 8192)}
    return SurfaceStudy.create(
        failure_snapshot_id="failure-1",
        mechanism_id="mechanism-1",
        parent_state_hash=STATE,
        partition=Partition.DEVELOPMENT,
        promotion_state=PromotionState.MOVEMENT,
        decision_id="D3",
        axes=axes,
        axis_values=values,
    )


def hypothesis(divergence=DivergenceClass.INSUFFICIENT_REASONING) -> CausalHypothesis:
    return CausalHypothesis.create(
        failure_snapshot_id="failure-1",
        parent_state_hash=STATE,
        divergence=FirstDivergence(
            divergence_class=divergence,
            observable_path="focus.semantic_pass",
            event_index=0,
            evidence_refs=("forensic:1",),
            confidence=0.9,
        ),
        owner_candidate=ArchitectureOwner.MODEL,
        claim="characterize the causal mechanism",
        expected_if_true="targeted surface treatment changes outcome",
        falsifier="targeted surface treatment does not change outcome",
    )


def intervention(kind=InterventionKind.COGNITION, hyp=None) -> InterventionDefinition:
    hyp = hyp or hypothesis()
    return InterventionDefinition.create(
        hypothesis_id=hyp.hypothesis_id,
        failure_snapshot_id="failure-1",
        parent_state_hash=STATE,
        kind=kind,
        label=f"surface-{kind.value.lower()}",
        expected_causal_implication="characterize the mechanism operating region",
        projected_physical_calls=2,
    )


def mechanism(hyp=None) -> MechanismLabel:
    hyp = hyp or hypothesis()
    return MechanismLabel(
        mechanism_label_id="label-1",
        failure_snapshot_id="failure-1",
        parent_failure_snapshot_id="failure-1",
        parent_state_hash=STATE,
        mechanism_id="mechanism-1",
        hypothesis_id=hyp.hypothesis_id,
        intervention_ids=("intervention-1",),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=("result-1",),
        confidence=0.9,
    )


@dataclass
class FakeStore:
    rows: tuple[SurfaceObservation, ...] = ()
    profile_rows: tuple[OperatingSurfaceProfile, ...] = ()

    def observations(self, study_id=None):
        if study_id is None:
            return self.rows
        return tuple(row for row in self.rows if row.study_id == study_id)

    def profiles(self, mechanism_id=None):
        if mechanism_id is None:
            return self.profile_rows
        return tuple(row for row in self.profile_rows if row.mechanism_id == mechanism_id)


class FakeCompiler:
    def __init__(self, store: FakeStore, answered=(), *, context=None):
        self.surface_store = store
        self._answered = frozenset(answered)
        self._context = context

    def answered_points(self, surface_study):
        return self._answered

    def mechanism_context(self, surface_study):
        if self._context is None:
            raise ValueError("no mechanism context")
        return self._context


def test_cognition_axes_gate_temperature_until_reasoning_is_causally_relevant() -> None:
    hyp = hypothesis()
    label = mechanism(hyp)
    cog = intervention(InterventionKind.COGNITION, hyp)
    axes = SurfacePlanner.eligible_axes(label, hyp, cog, cognition_relevant=False)
    assert axes == (SurfaceAxis.REASONING_BUDGET,)

    axes = SurfacePlanner.eligible_axes(label, hyp, cog, cognition_relevant=True)
    assert axes == (SurfaceAxis.REASONING_BUDGET, SurfaceAxis.TEMPERATURE)


def test_intervention_kind_limits_stage5_axes() -> None:
    hyp = hypothesis(DivergenceClass.CONTEXT_PRESSURE)
    label = mechanism(hyp)
    assert SurfacePlanner.eligible_axes(label, hyp, intervention(InterventionKind.CONTEXT, hyp)) == (
        SurfaceAxis.CONTEXT_DOSE, SurfaceAxis.CONTEXT_POSITION, SurfaceAxis.DELIVERY_MODE,
    )
    assert SurfacePlanner.eligible_axes(label, hyp, intervention(InterventionKind.REPRESENTATION, hyp)) == (
        SurfaceAxis.REPRESENTATION, SurfaceAxis.ORDER, SurfaceAxis.PLACEMENT,
    )
    assert SurfacePlanner.eligible_axes(label, hyp, intervention(InterventionKind.DELIVERY, hyp)) == (
        SurfaceAxis.TIMING, SurfaceAxis.RECURRENCE, SurfaceAxis.TRIGGER_MODE,
    )


def observation(surface_study, value, *, passed: bool) -> SurfaceObservation:
    point = SurfacePoint.create(
        study=surface_study,
        axis=SurfaceAxis.REASONING_BUDGET,
        value=value,
        decision_id="D3",
    )
    return SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
        replay_result_ids=(f"result-{value}",),
        metrics={
            "completed": True,
            "semantic_pass": passed,
            "contract_pass": True,
            "physical_calls": 1 if value == 0 else 2,
            "MODEL_CALLS": 0,
        },
    )


def point_id(surface_study, value) -> str:
    return SurfacePoint.create(
        study=surface_study,
        axis=SurfaceAxis.REASONING_BUDGET,
        value=value,
        decision_id="D3",
    ).surface_point_id


def test_budget_plan_reuses_answered_points_and_brackets_two_new_points() -> None:
    surface_study = study()
    answered = {
        point_id(surface_study, 0),
        point_id(surface_study, 1024),
    }
    store = FakeStore(rows=(observation(surface_study, 0, passed=False), observation(surface_study, 1024, passed=True)))
    planner = SurfacePlanner(store, FakeCompiler(store, answered))

    plan = planner.plan_next(surface_study, max_new_points=2)

    assert tuple(point.value for point in plan.points) == (256, 8192)
    assert plan.points[1].protected_exploration is True
    assert not answered.intersection(point.surface_point_id for point in plan.points)
    assert plan.stop_reason is None


def test_budget_call_geometry_is_adaptive_not_full_grid() -> None:
    surface_study = study()
    answered = {point_id(surface_study, 0), point_id(surface_study, 1024)}
    store = FakeStore(rows=(observation(surface_study, 0, passed=False), observation(surface_study, 1024, passed=True)))
    planner = SurfacePlanner(store, FakeCompiler(store, answered))

    plan = planner.plan_next(surface_study, max_new_points=2)

    assert plan.minimum_physical_calls == 4
    assert plan.expected_physical_calls <= plan.worst_case_physical_calls
    assert plan.protected_exploration_calls == 2
    assert plan.worst_case_physical_calls < 14


def test_existing_resolved_profile_stops_without_more_points() -> None:
    surface_study = study()
    band = SurfaceBand(
        axis=SurfaceAxis.REASONING_BUDGET,
        disposition=SurfaceDisposition.PLATEAU,
        lower_useful=512,
        upper_useful=8192,
        recommended_region=(512, 1024, 2048, 4096, 8192),
        harm_onset=None,
        evidence_observation_ids=("obs-a", "obs-b"),
        unresolved_edges=(),
    )
    profile = OperatingSurfaceProfile.create(
        study=surface_study,
        band=band,
        evidence_refs=("obs-a", "obs-b"),
        call_geometry=SurfaceCallGeometry(2, 4, 8, 2),
    )
    store = FakeStore(profile_rows=(profile,))
    planner = SurfacePlanner(store, FakeCompiler(store, ()))

    plan = planner.plan_next(surface_study, max_new_points=2)

    assert plan.points == ()
    assert plan.stop_reason == "surface already resolved as PLATEAU"
    assert plan.minimum_physical_calls == 0
    assert plan.expected_physical_calls == 0
    assert plan.worst_case_physical_calls == 0


def test_protected_extreme_survives_pruning_as_reserved_call_geometry() -> None:
    surface_study = study()
    answered = {point_id(surface_study, 0), point_id(surface_study, 1024)}
    store = FakeStore(rows=(observation(surface_study, 0, passed=False), observation(surface_study, 1024, passed=True)))
    planner = SurfacePlanner(store, FakeCompiler(store, answered))

    plan = planner.plan_next(surface_study, max_new_points=1)

    assert tuple(point.value for point in plan.points) == (256,)
    assert plan.protected_exploration_calls == 2
    assert "protected" in plan.decision_reason.lower()


def test_all_answered_points_stop_instead_of_increasing_sample_count() -> None:
    surface_study = study()
    answered = {point_id(surface_study, value) for value in surface_study.axis_values["REASONING_BUDGET"]}
    store = FakeStore()
    planner = SurfacePlanner(store, FakeCompiler(store, answered))

    plan = planner.plan_next(surface_study, max_new_points=2)

    assert plan.points == ()
    assert plan.stop_reason == "all registered surface points are already answered"
    assert plan.worst_case_physical_calls == 0
