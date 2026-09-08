from __future__ import annotations

from dataclasses import dataclass

import pytest

from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    InterventionDefinition,
    InterventionKind,
    MechanismRole,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
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
from inverted.capability_ratchet.mutation_core import (
    MutationAxis,
    MutationDirection,
    MutationOrigin,
)
from inverted.capability_ratchet.mutation_replay import MutationReplayCompiler
from inverted.capability_ratchet.replay import ReplayCompletion, ReplayExecutor
from inverted.capability_ratchet.replay_store import ReplayStore


PATH = "request_envelopes.0.messages.0.content"
REPAIR_SUFFIX = "\n\nDEPENDENCY STATE\nEnumerate visible prerequisites before choosing an action."


@dataclass
class Environment:
    replay: ReplayStore
    causal: CausalEvidenceStore
    source: FailureFixture
    mutation: MutationFixture
    hypothesis: CausalHypothesis
    intervention: InterventionDefinition
    mechanism: MechanismLabel


class RecordingAdapter:
    def __init__(self, *, passed: bool = True) -> None:
        self.passed = passed
        self.visible_payload = None
        self.fixture = None
        self.request = None

    def runtime_provenance(self):
        return {
            "provider": "fake",
            "model": "fake-model",
            "model_digest": "fake-digest",
        }

    def execute_fixture(self, fixture, visible_payload, request):
        self.fixture = fixture
        self.visible_payload = visible_payload
        self.request = request
        calls = tuple(
            {"request": envelope, "response": {"ok": self.passed}}
            for envelope in visible_payload["request_envelopes"]
        )
        return ReplayCompletion(
            completed=True,
            semantic_pass=self.passed,
            contract_pass=True,
            output_payload={"answer": "ok" if self.passed else "wrong"},
            raw_calls=calls,
            failure_classes=() if self.passed else ("SEMANTIC_FAIL",),
            metrics={"physical_calls": len(calls)},
        )


def _environment(tmp_path) -> Environment:
    replay = ReplayStore(tmp_path / "replay")
    source_visible = {
        "request_envelopes": [
            {
                "model": "fake-model",
                "stream": False,
                "think": False,
                "options": {
                    "seed": 7,
                    "num_predict": 128,
                    "temperature": 0.2,
                },
                "messages": [{"role": "user", "content": "BASE TASK"}],
                "tools": [{"type": "function", "function": {"name": "lookup"}}],
            }
        ]
    }
    source_visible_sha = replay.put_asset(source_visible)
    source_oracle_sha = replay.put_asset({"answer": "base"})
    source = FailureFixture(
        failure_snapshot_id="failure-mutation-replay",
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
        inference_profile={"thinking_budget": 0},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=source_visible_sha,
        state_hash="a" * 64,
        oracle_ref="oracle:base",
        expected_contract="return a valid plan",
        source_evidence_refs=("evidence:base",),
        oracle_asset_sha256=source_oracle_sha,
    )
    replay.append(source)
    source = replay.get_failure(source.failure_snapshot_id)

    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.MISSING_DEPENDENCY,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=("evidence:base",),
            confidence=0.95,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim="explicit dependency representation repairs this failure",
        expected_if_true="target succeeds while matched control fails",
        falsifier="target fails or control also succeeds",
    )
    causal.append_hypothesis(hypothesis)
    intervention = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        kind=InterventionKind.REPRESENTATION,
        label="proven dependency representation",
        changed_dimensions=(PATH,),
        overrides={PATH: "BASE TASK" + REPAIR_SUFFIX},
        expected_causal_implication=hypothesis.expected_if_true,
    )
    causal.register_intervention(intervention)

    movement_request = ReplayRequest(
        replay_request_id="movement-request",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        decision_id="D4",
        hypothesis_id=hypothesis.hypothesis_id,
        expected_causal_implication=intervention.expected_causal_implication,
        mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=source.source_model_id,
        source_model_digest=source.source_model_digest,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        changed_dimensions=intervention.changed_dimensions,
        intervention_id=intervention.intervention_id,
        overrides=intervention.overrides,
    )
    replay.append(movement_request)
    movement_output = replay.put_asset({"passed": True})
    movement_raw = replay.put_asset({"raw_calls": [{"request": source_visible["request_envelopes"][0]}]})
    movement_result = ReplayResult(
        replay_result_id="movement-result",
        replay_request_id=movement_request.replay_request_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mode=movement_request.mode,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        completed=True,
        semantic_pass=True,
        contract_pass=True,
        output_asset_sha256=movement_output,
        raw_call_asset_sha256=movement_raw,
        metadata={"intervention_id": intervention.intervention_id},
    )
    replay.append(movement_result)
    mechanism = MechanismLabel(
        mechanism_label_id="mechanism-label-proven",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="mechanism-proven",
        hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=(intervention.intervention_id,),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        confidence=0.95,
    )
    replay.append(mechanism)
    replay.append(
        PromotionEvent(
            promotion_event_id="movement-event-proven",
            failure_snapshot_id=source.failure_snapshot_id,
            mechanism_id=mechanism.mechanism_id,
            from_state=PromotionState.UNASSESSED,
            to_state=PromotionState.MOVEMENT,
            reason="matched causal target earned movement",
            evidence_replay_result_ids=(movement_result.replay_result_id,),
            partition=source.partition,
        )
    )

    mutation_visible = {
        "request_envelopes": [
            {
                "model": "fake-model",
                "stream": False,
                "think": False,
                "options": {
                    "seed": 7,
                    "num_predict": 128,
                    "temperature": 0.2,
                },
                "messages": [{"role": "user", "content": "MUTATED TASK"}],
                "tools": [{"type": "function", "function": {"name": "lookup"}}],
            }
        ]
    }
    mutation_visible_sha = replay.put_asset(mutation_visible)
    mutation_oracle_sha = replay.put_asset({"answer": "mutated"})
    mutation = MutationFixture.create(
        failure_snapshot_id=source.failure_snapshot_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        mechanism_id=mechanism.mechanism_id,
        mutation_axis=MutationAxis.NUMBERS_ENTITIES,
        mutation_direction=MutationDirection.HARDER,
        mutation_value={"entity": "MUTATED"},
        structural_region_id="region-a",
        model_visible_asset_sha256=mutation_visible_sha,
        oracle_asset_sha256=mutation_oracle_sha,
        semantic_contract_hash="3" * 64,
        partition=source.partition,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
        metadata={
            "mutation_spec_id": "mutation-spec-test",
            "protected": True,
            "operating_surface_profile_id": "surface-profile-1",
        },
    )
    replay.append(mutation)
    assert replay.validate().ok
    assert causal.validate().ok
    return Environment(replay, causal, source, mutation, hypothesis, intervention, mechanism)


def _compile(env: Environment) -> ReplayRequest:
    return MutationReplayCompiler(env.replay, env.causal).compile(
        env.mutation,
        env.mechanism,
        env.mechanism.intervention_ids,
        request_id="mutation-replay-request",
        decision_id="D12",
    )


def test_compiler_preserves_proven_mechanism_identity_and_declares_only_repair_leaves(tmp_path):
    env = _environment(tmp_path)

    request = _compile(env)

    assert request.mode is ReplayMode.COUNTERFACTUAL
    assert request.failure_snapshot_id == env.source.failure_snapshot_id
    assert request.parent_failure_snapshot_id == env.source.failure_snapshot_id
    assert request.parent_state_hash == env.source.state_hash
    assert request.intervention_id == env.intervention.intervention_id
    assert request.changed_dimensions == env.intervention.changed_dimensions
    assert set(request.overrides) == {PATH}
    assert request.overrides[PATH] == "MUTATED TASK" + REPAIR_SUFFIX
    assert request.metadata["mechanism_id"] == env.mechanism.mechanism_id
    assert tuple(request.metadata["mechanism_intervention_ids"]) == env.mechanism.intervention_ids
    assert request.metadata["mutation_fixture_id"] == env.mutation.mutation_fixture_id
    assert request.metadata["mutation_axis"] == env.mutation.mutation_axis.value
    assert request.metadata["mutation_direction"] == env.mutation.mutation_direction.value
    assert request.metadata["structural_region_id"] == env.mutation.structural_region_id
    assert request.metadata["synthetic_neighborhood"] is True
    assert request.metadata["operating_surface_profile_id"] == "surface-profile-1"


def test_executor_uses_mutated_fixture_then_applies_only_the_registered_repair(tmp_path):
    env = _environment(tmp_path)
    request = _compile(env)
    adapter = RecordingAdapter()

    plan = ReplayExecutor(env.replay, {"fake-model": adapter}).plan(request)

    envelope = plan.visible_payload["request_envelopes"][0]
    assert envelope["messages"][0]["content"] == "MUTATED TASK" + REPAIR_SUFFIX
    assert envelope["options"] == {"seed": 7, "num_predict": 128, "temperature": 0.2}
    assert envelope["think"] is False
    assert envelope["tools"] == [{"type": "function", "function": {"name": "lookup"}}]
    assert set(plan.changed_values) == {PATH}
    assert plan.changed_values[PATH] == ("MUTATED TASK", "MUTATED TASK" + REPAIR_SUFFIX)


def test_executor_propagates_mutation_provenance_to_canonical_result(tmp_path):
    env = _environment(tmp_path)
    request = _compile(env)
    adapter = RecordingAdapter()

    result = ReplayExecutor(env.replay, {"fake-model": adapter}).execute(request)

    assert result.semantic_pass and result.contract_pass
    assert result.metadata["mutation_fixture_id"] == env.mutation.mutation_fixture_id
    assert result.metadata["mechanism_id"] == env.mechanism.mechanism_id
    assert tuple(result.metadata["mechanism_intervention_ids"]) == env.mechanism.intervention_ids
    assert adapter.visible_payload["request_envelopes"][0]["messages"][0]["content"] == "MUTATED TASK" + REPAIR_SUFFIX
    assert env.replay.validate().ok


def test_failed_mutation_replay_creates_child_without_mutating_source_or_mutation_fixture(tmp_path):
    env = _environment(tmp_path)
    request = _compile(env)
    source_before = env.replay.get_failure(env.source.failure_snapshot_id)
    mutation_before = next(
        item for item in env.replay.records()
        if isinstance(item, MutationFixture) and item.mutation_fixture_id == env.mutation.mutation_fixture_id
    )

    result = ReplayExecutor(env.replay, {"fake-model": RecordingAdapter(passed=False)}).execute(request)

    assert result.child_failure_snapshot_id is not None
    child = env.replay.get_failure(result.child_failure_snapshot_id)
    assert child.parent_failure_snapshot_id == env.source.failure_snapshot_id
    assert child.parent_state_hash == env.source.state_hash
    assert child.oracle_asset_sha256 == env.mutation.oracle_asset_sha256
    assert child.metadata["mutation_fixture_id"] == env.mutation.mutation_fixture_id
    assert env.replay.get_failure(env.source.failure_snapshot_id) == source_before
    mutation_after = next(
        item for item in env.replay.records()
        if isinstance(item, MutationFixture) and item.mutation_fixture_id == env.mutation.mutation_fixture_id
    )
    assert mutation_after == mutation_before
    assert env.replay.validate().ok


def test_compiler_rejects_intervention_set_that_differs_from_movement_mechanism(tmp_path):
    env = _environment(tmp_path)

    with pytest.raises(ValueError, match="mechanism intervention"):
        MutationReplayCompiler(env.replay, env.causal).compile(
            env.mutation,
            env.mechanism,
            ("different-intervention",),
            request_id="mutation-replay-request-bad",
        )


def test_compiler_requires_a_canonical_movement_event_for_the_mechanism(tmp_path):
    env = _environment(tmp_path)
    not_moved = MechanismLabel(
        mechanism_label_id="unmoved-label",
        failure_snapshot_id=env.source.failure_snapshot_id,
        parent_failure_snapshot_id=env.source.failure_snapshot_id,
        parent_state_hash=env.source.state_hash,
        mechanism_id="mechanism-unmoved",
        hypothesis_id=env.hypothesis.hypothesis_id,
        intervention_ids=env.mechanism.intervention_ids,
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=env.mechanism.evidence_replay_result_ids,
        confidence=0.9,
    )
    env.replay.append(not_moved)

    with pytest.raises(ValueError, match="MOVEMENT"):
        MutationReplayCompiler(env.replay, env.causal).compile(
            env.mutation,
            not_moved,
            not_moved.intervention_ids,
            request_id="mutation-replay-request-unmoved",
        )
