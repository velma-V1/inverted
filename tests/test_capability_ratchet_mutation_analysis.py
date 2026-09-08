from __future__ import annotations

from types import SimpleNamespace

import pytest

from inverted.capability_ratchet.causal_core import MechanismRole
from inverted.capability_ratchet.core import (
    FailureFixture,
    MechanismLabel,
    MutationFixture,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.mutation_analysis import MutationAnalyzer
from inverted.capability_ratchet.mutation_core import (
    GeneralizationClass,
    MutationAxis,
    MutationDirection,
    MutationOrigin,
    MutationPolicy,
    MutationSpec,
)
from inverted.capability_ratchet.mutation_store import (
    MutationEvidenceStore,
    MutationOutcome,
    MutationStudy,
)
from inverted.capability_ratchet.query import ReplaySelector, select_failures
from inverted.capability_ratchet.replay_store import ReplayStore


PATH = "request_envelopes.0.messages.0.content"


class SurfaceStub:
    def profiles(self, mechanism_id=None):
        return ()

    def validate(self):
        return SimpleNamespace(ok=True)


def _source(replay: ReplayStore) -> FailureFixture:
    visible = replay.put_asset({
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 7},
            "messages": [{"role": "user", "content": "dependency-sensitive task"}],
        }]
    })
    source = FailureFixture(
        failure_snapshot_id="failure-root",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash="a" * 64,
        oracle_ref="oracle",
        expected_contract="answer",
        source_evidence_refs=("source:1",),
    )
    replay.append(source)
    return source


def _movement(replay: ReplayStore, source: FailureFixture) -> MechanismLabel:
    request = ReplayRequest(
        replay_request_id="request-baseline-repair",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        decision_id="D12",
        hypothesis_id="hypothesis-1",
        expected_causal_implication="repair succeeds",
        mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=source.source_model_id,
        source_model_digest=source.source_model_digest,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        changed_dimensions=(PATH,),
        intervention_id="intervention-1",
        overrides={PATH: "repaired dependency representation"},
    )
    replay.append(request)
    result = ReplayResult(
        replay_result_id="result-baseline-repair",
        replay_request_id=request.replay_request_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mode=request.mode,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        completed=True,
        semantic_pass=True,
        contract_pass=True,
        output_asset_sha256=replay.put_asset({"answer": "ok"}),
        raw_call_asset_sha256=replay.put_asset({"raw_calls": [{"request": "baseline"}]}),
    )
    replay.append(result)
    label = MechanismLabel(
        mechanism_label_id="label-mechanism-1",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="mechanism-1",
        hypothesis_id="hypothesis-1",
        intervention_ids=("intervention-1",),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(result.replay_result_id,),
        confidence=1.0,
    )
    replay.append(label)
    replay.append(PromotionEvent(
        promotion_event_id="promotion-movement",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=label.mechanism_id,
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="causal repair demonstrated",
        evidence_replay_result_ids=(result.replay_result_id,),
        partition=source.partition,
    ))
    return label


def _spec(axis, direction, region, value, *, protected=False):
    return MutationSpec(
        axis=axis,
        direction=direction,
        value=value,
        structural_region_id=region,
        decision_id="D12",
        protected=protected,
    )


def _case(tmp_path, specs, passes, *, policy=None):
    replay = ReplayStore(tmp_path / "replay")
    source = _source(replay)
    _movement(replay, source)
    mutation = MutationEvidenceStore(
        tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub()
    )
    study = MutationStudy(
        study_id="mutation-study-1",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id="mechanism-1",
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        operating_surface_profile_id=None,
        policy=MutationPolicy() if policy is None else policy,
        decision_id="D12",
        candidate_specs=tuple(specs),
        protected_spec_ids=tuple(spec.spec_id for spec in specs if spec.protected),
    )
    mutation.append_study(study)

    for index, (spec, passed) in enumerate(zip(specs, passes, strict=True), 1):
        visible_sha = replay.put_asset({
            "request_envelopes": [{
                "model": "fake-model",
                "stream": False,
                "think": False,
                "options": {"seed": 7},
                "messages": [{"role": "user", "content": f"mutated task {index}"}],
            }]
        })
        fixture = MutationFixture.create(
            failure_snapshot_id=source.failure_snapshot_id,
            source_failure_snapshot_id=source.failure_snapshot_id,
            source_state_hash=source.state_hash,
            mechanism_id="mechanism-1",
            mutation_axis=spec.axis,
            mutation_direction=spec.direction,
            mutation_value=spec.value,
            structural_region_id=spec.structural_region_id,
            model_visible_asset_sha256=visible_sha,
            oracle_asset_sha256=replay.put_asset({"answer": f"oracle-{index}"}),
            semantic_contract_hash="d" * 64,
            partition=source.partition,
            origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
            metadata={"mutation_spec_id": spec.spec_id, "protected": spec.protected},
        )
        replay.append(fixture)
        request = ReplayRequest(
            replay_request_id=f"request-mutation-{index}",
            failure_snapshot_id=source.failure_snapshot_id,
            parent_failure_snapshot_id=source.failure_snapshot_id,
            parent_state_hash=source.state_hash,
            decision_id="D12",
            hypothesis_id="hypothesis-1",
            expected_causal_implication="same repair transfers unchanged",
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=source.source_model_id,
            source_model_digest=source.source_model_digest,
            target_model_id=source.source_model_id,
            target_model_digest=source.source_model_digest,
            partition=source.partition,
            changed_dimensions=(PATH,),
            intervention_id="intervention-1",
            overrides={PATH: f"repair over mutation {index}"},
            metadata={"mutation_fixture_id": fixture.mutation_fixture_id},
        )
        replay.append(request)
        child_id = None
        failures = ()
        if not passed:
            failures = ("SEMANTIC_FAIL",)
            child_id = f"failure-mutation-{index}"
            replay.append(FailureFixture(
                failure_snapshot_id=child_id,
                source_campaign_id=source.source_campaign_id,
                source_trial_id=f"mutation:{index}",
                focus_observation_id=f"mutation-observation:{index}",
                focus_task_id=source.focus_task_id,
                batch_task_ids=source.batch_task_ids,
                family=source.family,
                failure_classes=failures,
                source_model_id=source.source_model_id,
                source_model_digest=source.source_model_digest,
                source_runtime=source.source_runtime,
                inference_profile=source.inference_profile,
                inference_seed=source.inference_seed,
                partition=source.partition,
                model_visible_asset_sha256=visible_sha,
                state_hash=f"{index:064x}",
                oracle_ref=source.oracle_ref,
                expected_contract=source.expected_contract,
                source_evidence_refs=(f"mutation:{index}",),
                parent_failure_snapshot_id=source.failure_snapshot_id,
                parent_state_hash=source.state_hash,
                metadata={"mutation_fixture_id": fixture.mutation_fixture_id},
            ))
        result = ReplayResult(
            replay_result_id=f"result-mutation-{index}",
            replay_request_id=request.replay_request_id,
            failure_snapshot_id=source.failure_snapshot_id,
            parent_failure_snapshot_id=source.failure_snapshot_id,
            parent_state_hash=source.state_hash,
            mode=request.mode,
            target_model_id=source.source_model_id,
            target_model_digest=source.source_model_digest,
            partition=source.partition,
            completed=True,
            semantic_pass=passed,
            contract_pass=True,
            output_asset_sha256=replay.put_asset({"passed": passed, "index": index}),
            raw_call_asset_sha256=replay.put_asset({"raw_calls": [{"request": index}]}),
            failure_classes=failures,
            child_failure_snapshot_id=child_id,
            metadata={"mutation_fixture_id": fixture.mutation_fixture_id},
        )
        replay.append(result)
        mutation.append_outcome(MutationOutcome(
            outcome_id=f"outcome-{index}",
            study_id=study.study_id,
            mutation_fixture_id=fixture.mutation_fixture_id,
            replay_result_id=result.replay_result_id,
            axis=spec.axis,
            direction=spec.direction,
            structural_region_id=spec.structural_region_id,
            protected=spec.protected,
            semantic_pass=passed,
            contract_pass=True,
        ))
    assert replay.validate().ok
    assert mutation.validate().ok
    return replay, mutation, study, source


def test_classifies_instance_patch_from_one_success(tmp_path):
    specs = (_spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, "planning/dependency", 3),)
    replay, mutation, study, _ = _case(tmp_path, specs, (True,))
    profile = MutationAnalyzer(replay, mutation).analyze(study.study_id)
    assert profile.classification is GeneralizationClass.INSTANCE_PATCH
    assert profile.success_rate == 1.0


def test_classifies_local_mechanism_from_two_same_axis_successes(tmp_path):
    specs = (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, "planning/dependency", 3),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, "planning/dependency", 4),
    )
    replay, mutation, study, _ = _case(tmp_path, specs, (True, True))
    profile = MutationAnalyzer(replay, mutation).analyze(study.study_id)
    assert profile.classification is GeneralizationClass.LOCAL_MECHANISM


def test_classifies_region_mechanism_from_default_policy_breadth(tmp_path):
    specs = (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, "planning/dependency", 3),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.LATERAL, "planning/dependency", 4),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, "planning/dependency", 1),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, "planning/dependency", 5),
    )
    replay, mutation, study, _ = _case(tmp_path, specs, (True,) * 4)
    profile = MutationAnalyzer(replay, mutation).analyze(study.study_id)
    assert profile.classification is GeneralizationClass.REGION_MECHANISM


def test_classifies_cross_region_mechanism_before_promotion_thresholds(tmp_path):
    specs = (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, "planning/dependency", 3),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.LATERAL, "planning/dependency", 4),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, "planning/dependency", 1),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, "planning/action", 4),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.LATERAL, "planning/action", 5),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, "planning/action", 2),
    )
    replay, mutation, study, _ = _case(tmp_path, specs, (True,) * 6)
    profile = MutationAnalyzer(replay, mutation).analyze(study.study_id)
    assert profile.classification is GeneralizationClass.CROSS_REGION_MECHANISM


def _promotion_specs(*, protected_failure=False):
    return (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, "planning/dependency", 4),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.HARDER, "planning/dependency", 5),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, "planning/dependency", 2),
        _spec(MutationAxis.ORDER, MutationDirection.LATERAL, "planning/dependency", "reverse"),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, "planning/action", 3),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.LATERAL, "planning/action", 6),
        _spec(
            MutationAxis.CONTEXT_PRESSURE,
            MutationDirection.HARDER,
            "planning/action",
            2,
            protected=protected_failure,
        ),
    )


def test_promotion_candidate_emits_only_movement_to_tier_candidate(tmp_path):
    specs = _promotion_specs()
    replay, mutation, study, source = _case(tmp_path, specs, (True,) * len(specs))
    analyzer = MutationAnalyzer(replay, mutation)
    profile = analyzer.analyze(study.study_id)
    assert profile.classification is GeneralizationClass.PROMOTION_CANDIDATE
    event = analyzer.maybe_promote(profile)
    assert event is not None
    assert event.from_state is PromotionState.MOVEMENT
    assert event.to_state is PromotionState.TIER_CANDIDATE
    assert replay.get_failure(source.failure_snapshot_id).promotion_state is PromotionState.UNASSESSED
    assert replay.validate().ok

    selected = select_failures(
        replay,
        ReplaySelector(promotion_state=PromotionState.TIER_CANDIDATE, mechanism="mechanism-1"),
    )
    assert [item.failure_snapshot_id for item in selected] == [source.failure_snapshot_id]


def test_protected_negative_transfer_blocks_promotion_and_remains_boundary(tmp_path):
    specs = _promotion_specs(protected_failure=True)
    passes = (True,) * (len(specs) - 1) + (False,)
    replay, mutation, study, _ = _case(tmp_path, specs, passes)
    analyzer = MutationAnalyzer(replay, mutation)
    profile = analyzer.analyze(study.study_id)
    assert profile.classification is not GeneralizationClass.PROMOTION_CANDIDATE
    assert profile.protected_failures
    assert any("CONTEXT_PRESSURE" in boundary for boundary in profile.unresolved_boundaries)
    assert analyzer.maybe_promote(profile) is None
    assert not any(
        isinstance(record, PromotionEvent) and record.to_state is PromotionState.TIER_CANDIDATE
        for record in replay.records()
    )


def test_registered_policy_can_explicitly_allow_one_protected_failure(tmp_path):
    specs = _promotion_specs(protected_failure=True)
    passes = (True,) * (len(specs) - 1) + (False,)
    relaxed = MutationPolicy(max_protected_failures=1)
    replay, mutation, study, _ = _case(tmp_path, specs, passes, policy=relaxed)
    analyzer = MutationAnalyzer(replay, mutation)
    profile = analyzer.analyze(study.study_id)
    assert profile.protected_failures
    assert profile.classification is GeneralizationClass.PROMOTION_CANDIDATE
    event = analyzer.maybe_promote(profile)
    assert event is not None
    assert event.to_state is PromotionState.TIER_CANDIDATE


def test_stage6_never_emits_certified(tmp_path):
    specs = _promotion_specs()
    replay, mutation, study, _ = _case(tmp_path, specs, (True,) * len(specs))
    analyzer = MutationAnalyzer(replay, mutation)
    event = analyzer.maybe_promote(analyzer.analyze(study.study_id))
    assert event is not None
    assert event.to_state is not PromotionState.CERTIFIED
    with pytest.raises(ValueError):
        analyzer._promotion_event(  # noqa: SLF001 - explicit Stage-6 ceiling contract
            analyzer.analyze(study.study_id),
            from_state=PromotionState.TIER_CANDIDATE,
            to_state=PromotionState.CERTIFIED,
        )
