from __future__ import annotations

from dataclasses import replace

import pytest

from inverted.capability_ratchet.core import (
    FailureFixture,
    MutationFixture,
    Partition,
    PromotionState,
    ReplayRecordType,
)
from inverted.capability_ratchet.mutation_core import (
    GeneralizationClass,
    GeneralizationProfile,
    MutationAxis,
    MutationDirection,
    MutationOrigin,
    MutationPolicy,
    MutationSpec,
)
from inverted.capability_ratchet.replay_store import ReplayStore


EXPECTED_AXES = {
    "NUMBERS_ENTITIES",
    "DEPENDENCY_DEPTH",
    "REQUIREMENT_COUNT",
    "ACTION_SPACE_SIZE",
    "CRITICAL_INFORMATION_POSITION",
    "DISTRACTORS",
    "EVIDENCE_STATE",
    "AUTHORITY_STATE",
    "REVERSIBILITY_CONSEQUENCE",
    "TOOL_AVAILABILITY",
    "CONTEXT_PRESSURE",
    "ORDER",
    "RECOVERY_OPPORTUNITY",
}
EXPECTED_CLASSES = {
    "INSTANCE_PATCH",
    "LOCAL_MECHANISM",
    "REGION_MECHANISM",
    "CROSS_REGION_MECHANISM",
    "PROMOTION_CANDIDATE",
}


def _failure(store: ReplayStore, *, failure_id: str = "failure-root", partition: Partition = Partition.DEVELOPMENT) -> FailureFixture:
    visible = store.put_asset({"messages": [{"role": "user", "content": "solve"}]})
    return FailureFixture(
        failure_snapshot_id=failure_id,
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="observation",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0},
        inference_seed=7,
        partition=partition,
        model_visible_asset_sha256=visible,
        state_hash="a" * 64,
        oracle_ref="oracle",
        expected_contract="answer",
        source_evidence_refs=("source:1",),
    )


def _mutation(store: ReplayStore, source: FailureFixture, **changes: object) -> MutationFixture:
    visible = store.put_asset({"messages": [{"role": "user", "content": "solve deeper"}]})
    oracle = store.put_asset({"answer": "ok"})
    values = dict(
        failure_snapshot_id=source.failure_snapshot_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        mechanism_id="mechanism-1",
        mutation_axis=MutationAxis.DEPENDENCY_DEPTH,
        mutation_direction=MutationDirection.HARDER,
        mutation_value={"depth": 4},
        structural_region_id="planning/dependency",
        model_visible_asset_sha256=visible,
        oracle_asset_sha256=oracle,
        semantic_contract_hash="d" * 64,
        partition=source.partition,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
    )
    values.update(changes)
    return MutationFixture.create(**values)  # type: ignore[arg-type]


def test_stage6_contracts_freeze_exact_axes_classes_directions_and_origins() -> None:
    assert {item.value for item in MutationAxis} == EXPECTED_AXES
    assert {item.value for item in GeneralizationClass} == EXPECTED_CLASSES
    assert {item.value for item in MutationDirection} == {"EASIER", "LATERAL", "HARDER"}
    assert {item.value for item in MutationOrigin} == {"SYNTHETIC_NEIGHBORHOOD", "NATURAL_OBSERVATION"}


def test_mutation_policy_defaults_are_explicit_and_stage6_ceiling_is_tier_candidate() -> None:
    policy = MutationPolicy()
    assert policy.min_local_successes == 2
    assert policy.min_region_successes == 4
    assert policy.min_region_axes == 3
    assert policy.min_cross_region_successes == 6
    assert policy.min_cross_regions == 2
    assert policy.min_promotion_successes == 6
    assert policy.min_promotion_axes == 4
    assert policy.min_harder_successes == 2
    assert policy.min_success_rate == 0.80
    assert policy.max_protected_failures == 0

    profile = GeneralizationProfile(
        profile_id="generalization-profile-1",
        study_id="study-1",
        failure_snapshot_id="failure-root",
        mechanism_id="mechanism-1",
        policy=policy,
        mutation_result_ids=("result-1",),
        successful_mutation_fixture_ids=("mutation-1",),
        failed_mutation_fixture_ids=(),
        axis_successes={MutationAxis.DEPENDENCY_DEPTH.value: 1},
        region_successes={"planning/dependency": 1},
        harder_successes=1,
        success_rate=1.0,
        protected_failures=(),
        classification=GeneralizationClass.INSTANCE_PATCH,
        unresolved_boundaries=(),
    )
    assert profile.promotion_ceiling is PromotionState.TIER_CANDIDATE


def test_mutation_spec_has_deterministic_identity_and_rejects_unstable_values() -> None:
    left = MutationSpec(
        axis=MutationAxis.DEPENDENCY_DEPTH,
        direction=MutationDirection.HARDER,
        value={"depth": 4, "labels": ["a", "b"]},
        structural_region_id="planning/dependency",
        decision_id="D12",
        protected=True,
    )
    right = MutationSpec(
        axis=MutationAxis.DEPENDENCY_DEPTH,
        direction=MutationDirection.HARDER,
        value={"labels": ["a", "b"], "depth": 4},
        structural_region_id="planning/dependency",
        decision_id="D12",
        protected=True,
    )
    assert left.spec_id == right.spec_id
    with pytest.raises((TypeError, ValueError)):
        MutationSpec(
            axis=MutationAxis.NUMBERS_ENTITIES,
            direction=MutationDirection.LATERAL,
            value={"bad": {1, 2}},
            structural_region_id="arithmetic",
            decision_id="D12",
        )


def test_mutation_fixture_requires_root_and_source_lineage_and_has_deterministic_id(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    source = _failure(store)
    store.append(source)

    first = _mutation(store, source)
    second = _mutation(store, source)

    assert first.record_type is ReplayRecordType.MUTATION_FIXTURE
    assert first.mutation_fixture_id == second.mutation_fixture_id
    assert first.failure_snapshot_id == source.failure_snapshot_id
    assert first.source_failure_snapshot_id == source.failure_snapshot_id
    assert first.source_state_hash == source.state_hash


def test_replay_store_round_trips_canonical_mutation_fixture_and_assets(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    source = _failure(store)
    store.append(source)
    mutation = _mutation(store, source)
    record_id = store.append(mutation)

    records = store.records()
    stored = next(record for record in records if isinstance(record, MutationFixture))
    assert stored == replace(mutation, record_id=record_id)
    assert store.validate().ok


def test_replay_store_rejects_missing_source_or_wrong_source_state_for_mutation(tmp_path) -> None:
    missing_store = ReplayStore(tmp_path / "missing")
    source = _failure(missing_store)
    mutation = _mutation(missing_store, source)
    missing_store.append(mutation)
    report = missing_store.validate()
    assert not report.ok
    assert any("source failure" in item for item in report.broken_lineage)

    wrong_store = ReplayStore(tmp_path / "wrong")
    source = _failure(wrong_store)
    wrong_store.append(source)
    wrong_store.append(_mutation(wrong_store, source, source_state_hash="f" * 64))
    report = wrong_store.validate()
    assert not report.ok
    assert any("source state" in item for item in report.broken_lineage)


def test_synthetic_mutations_cannot_use_fresh_or_sealed_partitions(tmp_path) -> None:
    for partition in (Partition.FRESH, Partition.SEALED):
        store = ReplayStore(tmp_path / partition.value.lower())
        source = _failure(store, partition=partition)
        store.append(source)
        with pytest.raises(ValueError, match="FRESH|SEALED|synthetic"):
            _mutation(store, source)


def test_natural_observation_may_be_recorded_without_synthetic_partition_relabeling(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    source = _failure(store, partition=Partition.FRESH)
    store.append(source)
    observed = _mutation(store, source, origin=MutationOrigin.NATURAL_OBSERVATION)
    store.append(observed)
    assert store.validate().ok
