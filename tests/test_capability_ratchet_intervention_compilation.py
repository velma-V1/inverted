from __future__ import annotations

import pytest

from inverted.capability_ratchet import FailureFixture, Partition, ReplayMode
from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    InterventionKind,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.interventions import InterventionGenerator
from inverted.capability_ratchet.replay_store import ReplayStore


def _fixture(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({
        "request_envelopes": [{
            "model": "model",
            "stream": False,
            "think": False,
            "options": {"seed": 5, "temperature": 0.7, "num_predict": 128},
            "messages": [{"role": "user", "content": "Build a plan from the recorded state."}],
            "tools": [],
        }]
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-dependency",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="model",
        source_model_digest="digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0.7},
        inference_seed=5,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash="7" * 64,
        oracle_ref="oracle",
        expected_contract="plan",
        source_evidence_refs=("raw:1",),
    )
    replay.append(fixture)
    return replay.get_failure(fixture.failure_snapshot_id), replay


def _hypothesis(fixture, divergence, *, owner=ArchitectureOwner.SYSTEM):
    return CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=divergence,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=("fixture:observable",),
            confidence=0.8,
        ),
        owner_candidate=owner,
        claim=f"{divergence.value} explains the failure",
        expected_if_true="the targeted treatment repairs the same parent state",
        falsifier="the targeted treatment fails while its matched alternative succeeds",
    )


def test_dependency_hypothesis_generates_representation_and_public_sham(tmp_path) -> None:
    fixture, replay = _fixture(tmp_path)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = _hypothesis(fixture, DivergenceClass.MISSING_DEPENDENCY)
    causal.append_hypothesis(hypothesis)
    generator = InterventionGenerator(replay, causal)

    target = generator.generate(fixture, hypothesis)[0]
    sham = generator.make_matched_sham(target)

    assert target.kind is InterventionKind.REPRESENTATION
    assert target.changed_dimensions == ("request_envelopes.0.messages.0.content",)
    assert "DEPENDENCY STATE" in target.overrides[target.changed_dimensions[0]]
    assert sham is not None
    assert sham.kind is InterventionKind.SHAM
    assert sham.sham_for == target.intervention_id
    assert sham.changed_dimensions == target.changed_dimensions


def test_model_visible_treatment_compiles_to_counterfactual_request(tmp_path) -> None:
    fixture, replay = _fixture(tmp_path)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = _hypothesis(fixture, DivergenceClass.MISSING_STATE)
    causal.append_hypothesis(hypothesis)
    generator = InterventionGenerator(replay, causal)
    target = generator.generate(fixture, hypothesis)[0]

    request = generator.compile_request(
        fixture,
        target,
        request_id="replay-request-dependency",
        decision_id="D-dependency",
    )

    assert request.mode is ReplayMode.COUNTERFACTUAL
    assert request.failure_snapshot_id == fixture.failure_snapshot_id
    assert request.parent_failure_snapshot_id == fixture.failure_snapshot_id
    assert request.parent_state_hash == fixture.state_hash
    assert request.hypothesis_id == hypothesis.hypothesis_id
    assert request.intervention_id == target.intervention_id
    assert request.changed_dimensions == target.changed_dimensions
    assert dict(request.overrides) == dict(target.overrides)


def test_zero_model_call_treatment_cannot_be_compiled_as_fake_model_replay(tmp_path) -> None:
    fixture, replay = _fixture(tmp_path)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = _hypothesis(fixture, DivergenceClass.DETERMINISTIC_COMPUTATION)
    causal.append_hypothesis(hypothesis)
    generator = InterventionGenerator(replay, causal)
    target = generator.generate(fixture, hypothesis)[0]
    assert target.kind is InterventionKind.DETERMINISTIC
    assert target.projected_physical_calls == 0
    assert generator.make_matched_sham(target) is None
    with pytest.raises(ValueError, match="zero-model-call"):
        generator.compile_request(fixture, target, request_id="req-zero", decision_id="D-zero")
