from __future__ import annotations

from inverted.capability_ratchet import FailureFixture, Partition
from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    InterventionDefinition,
    InterventionKind,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.replay_store import ReplayStore


def seeded_replay_store(root):
    store = ReplayStore(root)
    visible = store.put_asset({"request_envelopes": [{"model": "model", "messages": []}]})
    fixture = FailureFixture(
        failure_snapshot_id="failure-causal", source_campaign_id="campaign", source_trial_id="trial",
        focus_observation_id="obs", focus_task_id="task", batch_task_ids=("task",), family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="model", source_model_digest="digest",
        source_runtime={"provider": "fake"}, inference_profile={"temperature": 0}, inference_seed=1,
        partition=Partition.DEVELOPMENT, model_visible_asset_sha256=visible, state_hash="1" * 64,
        oracle_ref="oracle", expected_contract="answer", source_evidence_refs=("raw:1",),
    )
    store.append(fixture)
    return store, fixture


def hypothesis_for(fixture):
    return CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.DETERMINISTIC_COMPUTATION,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=("forensic:focus_observation",),
            confidence=0.8,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim="deterministic computation can remove the model-owned arithmetic step",
        expected_if_true="system computation repairs the same parent state",
        falsifier="deterministic computation fails to repair the same parent state",
    )


def intervention_for(fixture, hypothesis):
    return InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=InterventionKind.DETERMINISTIC,
        label="system-calculator",
        expected_causal_implication="system computation supplies the exact arithmetic result",
        projected_physical_calls=0,
    )


def test_intervention_registry_is_content_addressed_and_immutable(tmp_path) -> None:
    replay, fixture = seeded_replay_store(tmp_path / "replay")
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = hypothesis_for(fixture)
    causal.append_hypothesis(hypothesis)
    intervention = intervention_for(fixture, hypothesis)

    digest = causal.register_intervention(intervention)
    before = causal.intervention_registry_path.read_bytes()
    assert causal.register_intervention(intervention) == digest
    assert causal.intervention_registry_path.read_bytes() == before
    assert causal.get_intervention(intervention.intervention_id) == intervention
    assert causal.validate().ok
