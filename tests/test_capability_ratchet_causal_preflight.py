from __future__ import annotations

from dataclasses import replace

import pytest

from inverted.capability_ratchet.autopsy import FailureAutopsy
from inverted.capability_ratchet.causal_core import (
    DivergenceClass,
    InterventionDefinition,
    InterventionKind,
    MechanismRole,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.core import FailureFixture, Partition, PromotionState
from inverted.capability_ratchet.interventions import InterventionGenerator
from inverted.capability_ratchet.lab import FailureLab
from inverted.capability_ratchet.mechanisms import MechanismLocalizer
from inverted.capability_ratchet.replay import ReplayCompletion, ReplayExecutor
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.tournament import TournamentPlanner, build_ablations


class DependencyAdapter:
    def __init__(self, mode="planted"):
        self.mode = mode
        self.calls = 0

    def runtime_provenance(self):
        return {"model": "fake-model", "model_digest": "fake-digest", "provider": "fake"}

    def execute_fixture(self, fixture, visible_payload, request):
        self.calls += 1
        envelope = visible_payload["request_envelopes"][0]
        content = envelope["messages"][-1]["content"]
        if self.mode == "always-pass":
            passed = True
        elif self.mode == "always-fail":
            passed = False
        else:
            passed = "DEPENDENCY STATE" in content and "CONTROL CHECK" not in content
        return ReplayCompletion(
            completed=True,
            semantic_pass=passed,
            contract_pass=True,
            output_payload={"passed": passed, "request_id": request.replay_request_id},
            raw_calls=({"request": envelope, "response": {"passed": passed}},),
            failure_classes=() if passed else ("SEMANTIC_FAIL",),
            metrics={"physical_calls": 1, "adapter": "fake"},
        )


def _fixture(store: ReplayStore, *, snapshot="failure-planted", partition=Partition.DEVELOPMENT,
             dependency=True):
    visible = store.put_asset({
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 17, "num_predict": 128},
            "messages": [{
                "role": "user",
                "content": "Choose the next action while respecting all prerequisites.",
            }],
        }]
    })
    failures = ("SEMANTIC_FAIL", "MISSING_DEPENDENCY") if dependency else ("SEMANTIC_FAIL",)
    metadata = {"difficulty": 4}
    if dependency:
        metadata["dependency_state_missing"] = True
    item = FailureFixture(
        failure_snapshot_id=snapshot,
        source_campaign_id="plan2-preflight",
        source_trial_id=f"trial-{snapshot}",
        focus_observation_id=f"obs-{snapshot}",
        focus_task_id=f"task-{snapshot}",
        batch_task_ids=(f"task-{snapshot}",),
        family="PLANNING_DEPENDENCIES",
        failure_classes=failures,
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0},
        inference_seed=17,
        partition=partition,
        model_visible_asset_sha256=visible,
        state_hash=visible,
        oracle_ref=f"oracle:{snapshot}",
        expected_contract="dependency-aware next action",
        source_evidence_refs=(f"source:{snapshot}",),
        metadata=metadata,
    )
    store.append(item)
    return store.get_failure(snapshot)


def _lab(tmp_path, *, partition=Partition.DEVELOPMENT, dependency=True, snapshot="failure-planted"):
    replay = ReplayStore(tmp_path / "replay")
    fixture = _fixture(replay, snapshot=snapshot, partition=partition, dependency=dependency)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    lab = FailureLab(
        replay,
        causal,
        FailureAutopsy(replay, causal),
        InterventionGenerator(replay, causal),
        TournamentPlanner(causal),
        MechanismLocalizer(replay, causal),
    )
    return lab, fixture, replay, causal


def _forbid_live_transport(monkeypatch):
    import urllib.request
    from inverted.universal_tuning import qwen_ollama

    monkeypatch.setattr(
        qwen_ollama.QwenOllamaAdapter,
        "__init__",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("real Qwen constructor forbidden")),
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network forbidden")),
    )


def test_planted_dependency_mechanism_is_recovered_and_sham_rejected(tmp_path, monkeypatch):
    _forbid_live_transport(monkeypatch)
    lab, root, replay, _ = _lab(tmp_path)
    original = replay.get_failure(root.failure_snapshot_id)
    original_registry = replay.registry_path.read_bytes()

    program = lab.prepare(root.failure_snapshot_id)
    assert program.model_calls == 0
    assert program.autopsy.first_divergence.divergence_class is DivergenceClass.MISSING_DEPENDENCY
    assert any(item.kind is InterventionKind.REPRESENTATION for item in program.interventions)
    assert any(item.kind is InterventionKind.SHAM for item in program.interventions)
    assert replay.registry_path.read_bytes() == original_registry

    adapter = DependencyAdapter()
    result = lab.execute(program, adapters={"fake-model": adapter})

    assert result.target_results and any(item.semantic_pass for item in result.target_results)
    assert result.sham_results and not any(item.semantic_pass for item in result.sham_results)
    assert result.assessment.supported_hypotheses
    assert any(label.role in {MechanismRole.REQUIRED, MechanismRole.ENABLER}
               for label in result.assessment.labels)
    assert any(event.to_state is PromotionState.MOVEMENT for event in result.assessment.promotion_events)
    assert not any(event.to_state in {PromotionState.TIER_CANDIDATE, PromotionState.CERTIFIED}
                   for event in result.assessment.promotion_events)
    assert result.child_failure_snapshot_ids
    assert adapter.calls == len(program.replay_requests)
    assert result.model_calls_are_fake_only
    assert replay.get_failure(root.failure_snapshot_id) == original
    assert replay.validate().ok


def test_target_and_sham_both_passing_remains_unresolved(tmp_path):
    lab, root, _, _ = _lab(tmp_path)
    result = lab.execute(lab.prepare(root.failure_snapshot_id),
                         adapters={"fake-model": DependencyAdapter("always-pass")})
    assert not result.assessment.supported_hypotheses
    assert any(label.role is MechanismRole.UNRESOLVED for label in result.assessment.labels)
    assert not result.assessment.promotion_events


def test_target_failure_never_earns_movement_and_failed_child_is_preserved(tmp_path):
    lab, root, replay, _ = _lab(tmp_path)
    original = replay.get_failure(root.failure_snapshot_id)
    result = lab.execute(lab.prepare(root.failure_snapshot_id),
                         adapters={"fake-model": DependencyAdapter("always-fail")})
    assert not result.assessment.promotion_events
    assert result.child_failure_snapshot_ids
    for child_id in result.child_failure_snapshot_ids:
        child = replay.get_failure(child_id)
        assert child.parent_failure_snapshot_id == root.failure_snapshot_id
        assert child.parent_state_hash == root.state_hash
    assert replay.get_failure(root.failure_snapshot_id) == original
    assert replay.validate().ok


def test_partition_contamination_is_rejected_before_adapter_call(tmp_path):
    lab, root, replay, _ = _lab(tmp_path, partition=Partition.HISTORICAL)
    program = lab.prepare(root.failure_snapshot_id)
    request = replace(program.replay_requests[0], partition=Partition.SEALED)
    adapter = DependencyAdapter()
    with pytest.raises(ValueError, match="partition|parent"):
        ReplayExecutor(replay, {"fake-model": adapter}).execute(request)
    assert adapter.calls == 0
    assert replay.get_failure(root.failure_snapshot_id).partition is Partition.HISTORICAL


def test_protected_exploration_survives_tournament_pruning(tmp_path):
    lab, root, _, _ = _lab(tmp_path, dependency=False, snapshot="failure-protected")
    program = lab.prepare(root.failure_snapshot_id)
    assert program.autopsy.hypotheses
    assert any(item.protected_exploration for item in program.autopsy.hypotheses)
    protected_ids = {item.hypothesis_id for item in program.autopsy.hypotheses if item.protected_exploration}
    selected_ids = {branch.hypothesis_id for branch in program.tournament.branches}
    assert protected_ids <= selected_ids


def test_compound_geometry_is_leave_one_out_not_power_set(tmp_path):
    _, root, _, _ = _lab(tmp_path)
    compound = InterventionDefinition.create(
        hypothesis_id="hyp-compound",
        failure_snapshot_id=root.failure_snapshot_id,
        parent_state_hash=root.state_hash,
        kind=InterventionKind.REPRESENTATION,
        label="A+B+A",
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        overrides={"request_envelopes.0.messages.0.content": "compound"},
        expected_causal_implication="compound repairs the failure",
        projected_physical_calls=1,
        composition=("A", "B", "A"),
    )
    generated = build_ablations(compound, compound.composition)
    ablations = [item for item in generated if item.kind is InterventionKind.ABLATION]
    shams = [item for item in generated if item.kind is InterventionKind.SHAM]
    assert len(ablations) == 2
    assert {item.ablates for item in ablations} == {("A",), ("B",)}
    assert len(shams) == 1
    assert shams[0].composition == ("A", "B", "A")
