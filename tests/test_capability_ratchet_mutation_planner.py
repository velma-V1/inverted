from __future__ import annotations

from dataclasses import dataclass

import pytest

from inverted.capability_ratchet.core import MutationFixture, MutationOrigin, Partition
from inverted.capability_ratchet.mutation_core import (
    GeneralizationClass,
    GeneralizationProfile,
    MutationAxis,
    MutationDirection,
    MutationPolicy,
    MutationSpec,
)
from inverted.capability_ratchet.mutation_planner import MutationPlan, MutationPlanner
from inverted.capability_ratchet.mutation_store import MutationOutcome, MutationStudy


@dataclass
class ReplayStub:
    fixtures: tuple[MutationFixture, ...] = ()

    def records(self):
        return self.fixtures


class MutationStoreStub:
    def __init__(self, *, fixtures=(), outcomes=(), profiles=()):
        self.replay_store = ReplayStub(tuple(fixtures))
        self._outcomes = tuple(outcomes)
        self._profiles = tuple(profiles)

    def outcomes(self, study_id=None):
        if study_id is None:
            return self._outcomes
        return tuple(item for item in self._outcomes if item.study_id == study_id)

    def profiles(self, study_id=None):
        if study_id is None:
            return self._profiles
        return tuple(item for item in self._profiles if item.study_id == study_id)


def spec(
    axis: MutationAxis,
    value,
    *,
    direction: MutationDirection = MutationDirection.LATERAL,
    region: str = "region-a",
    protected: bool = False,
) -> MutationSpec:
    return MutationSpec(
        axis=axis,
        direction=direction,
        value=value,
        structural_region_id=region,
        decision_id="D12",
        protected=protected,
    )


def study(*specs: MutationSpec, policy: MutationPolicy | None = None) -> MutationStudy:
    protected = tuple(item.spec_id for item in specs if item.protected)
    return MutationStudy(
        study_id="mutation-study-1",
        failure_snapshot_id="root-failure",
        mechanism_id="mechanism-1",
        source_failure_snapshot_id="source-failure",
        source_state_hash="a" * 64,
        operating_surface_profile_id=None,
        policy=policy or MutationPolicy(),
        decision_id="D12",
        candidate_specs=tuple(specs),
        protected_spec_ids=protected,
        decision_critical_reason="resolve Stage-6 D12 generalization boundary",
    )


def fixture_for(study: MutationStudy, item: MutationSpec) -> MutationFixture:
    return MutationFixture.create(
        failure_snapshot_id=study.failure_snapshot_id,
        source_failure_snapshot_id=study.source_failure_snapshot_id,
        source_state_hash=study.source_state_hash,
        mechanism_id=study.mechanism_id,
        mutation_axis=item.axis,
        mutation_direction=item.direction,
        mutation_value=item.value,
        structural_region_id=item.structural_region_id,
        model_visible_asset_sha256="1" * 64,
        oracle_asset_sha256="2" * 64,
        semantic_contract_hash="3" * 64,
        partition=Partition.DEVELOPMENT,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
        metadata={"mutation_spec_id": item.spec_id, "protected": item.protected},
    )


def outcome_for(
    study: MutationStudy,
    fixture: MutationFixture,
    *,
    passed: bool = True,
    suffix: str = "1",
) -> MutationOutcome:
    return MutationOutcome(
        outcome_id=f"outcome-{suffix}",
        study_id=study.study_id,
        mutation_fixture_id=fixture.mutation_fixture_id,
        replay_result_id=f"result-{suffix}",
        axis=fixture.mutation_axis,
        direction=fixture.mutation_direction,
        structural_region_id=fixture.structural_region_id,
        protected=bool(fixture.metadata.get("protected", False)),
        semantic_pass=passed,
        contract_pass=passed,
    )


def profile(
    study: MutationStudy,
    classification: GeneralizationClass,
    *,
    axis_successes=None,
    region_successes=None,
    harder_successes: int = 0,
    success_rate: float = 1.0,
    protected_failures=(),
) -> GeneralizationProfile:
    return GeneralizationProfile(
        profile_id=f"profile-{classification.value.lower()}",
        study_id=study.study_id,
        failure_snapshot_id=study.failure_snapshot_id,
        mechanism_id=study.mechanism_id,
        policy=study.policy,
        mutation_result_ids=(),
        successful_mutation_fixture_ids=(),
        failed_mutation_fixture_ids=(),
        axis_successes=axis_successes or {},
        region_successes=region_successes or {},
        harder_successes=harder_successes,
        success_rate=success_rate,
        protected_failures=tuple(protected_failures),
        classification=classification,
        unresolved_boundaries=(),
    )


def test_initial_plan_spreads_across_axes_before_sampling_one_axis_densely():
    candidates = (
        spec(MutationAxis.NUMBERS_ENTITIES, 2),
        spec(MutationAxis.NUMBERS_ENTITIES, 3),
        spec(MutationAxis.NUMBERS_ENTITIES, 4),
        spec(MutationAxis.DEPENDENCY_DEPTH, 2),
        spec(
            MutationAxis.CONTEXT_PRESSURE,
            4096,
            direction=MutationDirection.HARDER,
            protected=True,
        ),
    )
    active = study(*candidates)

    plan = MutationPlanner(MutationStoreStub()).plan_next(active, max_new_mutations=3)

    assert isinstance(plan, MutationPlan)
    assert len(plan.specs) == 3
    assert len({item.axis for item in plan.specs}) == 3
    assert any(item.direction is MutationDirection.HARDER for item in plan.specs)
    assert candidates[-1] in plan.specs
    assert plan.minimum_physical_calls == 3
    assert plan.protected_challenge_calls == 1
    assert plan.minimum_physical_calls <= plan.expected_physical_calls <= plan.worst_case_physical_calls
    for item in plan.specs:
        assert item.spec_id in plan.decision_reason


def test_answered_mutation_fixture_is_reused_without_spending_a_new_call():
    answered = spec(MutationAxis.NUMBERS_ENTITIES, 2)
    fresh = spec(MutationAxis.DEPENDENCY_DEPTH, 2)
    active = study(answered, fresh)
    stored_fixture = fixture_for(active, answered)
    stored_outcome = outcome_for(active, stored_fixture)

    plan = MutationPlanner(
        MutationStoreStub(fixtures=(stored_fixture,), outcomes=(stored_outcome,))
    ).plan_next(active, max_new_mutations=2)

    assert plan.reused_fixture_ids == (stored_fixture.mutation_fixture_id,)
    assert plan.specs == (fresh,)
    assert plan.minimum_physical_calls == 1
    assert plan.expected_physical_calls == 1
    assert plan.worst_case_physical_calls == 1


def test_protected_harder_challenge_survives_pruning():
    protected = spec(
        MutationAxis.RECOVERY_OPPORTUNITY,
        False,
        direction=MutationDirection.HARDER,
        region="region-extreme",
        protected=True,
    )
    active = study(
        spec(MutationAxis.NUMBERS_ENTITIES, 2),
        spec(MutationAxis.DEPENDENCY_DEPTH, 2),
        spec(MutationAxis.REQUIREMENT_COUNT, 5),
        spec(MutationAxis.DISTRACTORS, 3),
        protected,
    )

    plan = MutationPlanner(MutationStoreStub()).plan_next(active, max_new_mutations=2)

    assert len(plan.specs) == 2
    assert protected in plan.specs
    assert plan.protected_challenge_calls == 1


def test_large_cartesian_candidate_pool_is_bounded_and_each_probe_is_decision_linked():
    candidates: list[MutationSpec] = []
    for index, axis in enumerate(MutationAxis):
        for value in range(3):
            candidates.append(
                spec(
                    axis,
                    value + 1,
                    direction=(
                        MutationDirection.HARDER
                        if value == 2
                        else MutationDirection.LATERAL
                    ),
                    region=f"region-{index % 3}",
                    protected=(value == 2 and index == len(MutationAxis) - 1),
                )
            )
    active = study(*candidates)

    plan = MutationPlanner(MutationStoreStub()).plan_next(active, max_new_mutations=3)

    assert len(candidates) == len(MutationAxis) * 3
    assert len(plan.specs) == 3
    assert plan.worst_case_physical_calls <= len(candidates)
    assert all(item.decision_id == "D12" for item in plan.specs)
    assert all(item.spec_id in plan.decision_reason for item in plan.specs)


def test_protected_failure_blocks_promotion_instead_of_being_averaged_away():
    remaining = spec(
        MutationAxis.ORDER,
        "reverse",
        direction=MutationDirection.HARDER,
        region="region-c",
    )
    active = study(remaining)
    current = profile(
        active,
        GeneralizationClass.CROSS_REGION_MECHANISM,
        axis_successes={
            MutationAxis.NUMBERS_ENTITIES.value: 2,
            MutationAxis.DEPENDENCY_DEPTH.value: 2,
            MutationAxis.REQUIREMENT_COUNT.value: 1,
            MutationAxis.CONTEXT_PRESSURE.value: 1,
        },
        region_successes={"region-a": 3, "region-b": 3},
        harder_successes=2,
        success_rate=0.95,
        protected_failures=("failed-protected-fixture",),
    )

    plan = MutationPlanner(MutationStoreStub(profiles=(current,))).plan_next(active)

    assert plan.specs == ()
    assert plan.stop_reason is not None
    assert "protected" in plan.stop_reason.lower()
    assert plan.minimum_physical_calls == 0


def test_stops_when_remaining_mutations_cannot_move_current_classification():
    remaining = spec(
        MutationAxis.NUMBERS_ENTITIES,
        99,
        direction=MutationDirection.LATERAL,
        region="region-a",
    )
    active = study(remaining)
    current = profile(
        active,
        GeneralizationClass.REGION_MECHANISM,
        axis_successes={
            MutationAxis.NUMBERS_ENTITIES.value: 2,
            MutationAxis.DEPENDENCY_DEPTH.value: 1,
            MutationAxis.REQUIREMENT_COUNT.value: 1,
        },
        region_successes={"region-a": 4},
        harder_successes=0,
    )

    plan = MutationPlanner(MutationStoreStub(profiles=(current,))).plan_next(active)

    assert plan.specs == ()
    assert plan.stop_reason is not None
    assert "cannot move" in plan.stop_reason.lower() or "settled" in plan.stop_reason.lower()
    assert plan.minimum_physical_calls == plan.expected_physical_calls == plan.worst_case_physical_calls == 0


def test_invalid_call_budget_is_rejected_without_touching_store():
    active = study(spec(MutationAxis.NUMBERS_ENTITIES, 2))
    planner = MutationPlanner(MutationStoreStub())

    with pytest.raises(ValueError, match="positive integer"):
        planner.plan_next(active, max_new_mutations=0)
