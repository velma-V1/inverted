from __future__ import annotations

from inverted.capability_ratchet.autopsy import FailureAutopsy
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.core import (
    FailureFixture,
    MechanismLabel,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.interventions import InterventionGenerator
from inverted.capability_ratchet.lab import FailureLab
from inverted.capability_ratchet.mechanisms import MechanismLocalizer
from inverted.capability_ratchet.replay import ReplayCompletion
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.tournament import TournamentPlanner


class PlantedAdapter:
    def runtime_provenance(self):
        return {
            "model": "fake-model",
            "model_digest": "fake-digest",
            "provider": "fake",
        }

    def execute_fixture(self, fixture, visible_payload, request):
        envelope = visible_payload["request_envelopes"][0]
        content = envelope["messages"][-1]["content"]
        passed = (
            "HYPOTHESIS-SEPARATING CHECK" in content
            and "CONTROL CHECK" not in content
        )
        return ReplayCompletion(
            completed=True,
            semantic_pass=passed,
            contract_pass=True,
            output_payload={"passed": passed, "request_id": request.replay_request_id},
            raw_calls=({
                "request": envelope,
                "response": {"passed": passed},
            },),
            failure_classes=() if passed else ("SEMANTIC_FAIL",),
            metrics={"physical_calls": 1, "adapter": "fake"},
        )


def planted_lab(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "num_predict": 128},
            "messages": [{
                "role": "user",
                "content": "Choose the correct dependency-sensitive action.",
            }],
        }]
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-lab-root",
        source_campaign_id="campaign-lab",
        source_trial_id="trial-root",
        focus_observation_id="obs-root",
        focus_task_id="task-root",
        batch_task_ids=("task-root",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash=visible,
        oracle_ref="oracle:root",
        expected_contract="plan",
        source_evidence_refs=("source:root",),
        metadata={"difficulty": 3},
    )
    replay.append(fixture)
    fixture = replay.get_failure(fixture.failure_snapshot_id)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    autopsy = FailureAutopsy(replay, causal)
    interventions = InterventionGenerator(replay, causal)
    planner = TournamentPlanner(causal)
    localizer = MechanismLocalizer(replay, causal)
    lab = FailureLab(replay, causal, autopsy, interventions, planner, localizer)
    return lab, fixture, replay, causal


def test_prepare_is_zero_call_deterministic_and_compiles_one_parent_state(tmp_path):
    lab, fixture, replay, causal = planted_lab(tmp_path)
    before = replay.registry_path.read_bytes()

    first = lab.prepare(fixture.failure_snapshot_id)
    second = lab.prepare(fixture.failure_snapshot_id)

    assert first == second
    assert first.failure_snapshot_id == fixture.failure_snapshot_id
    assert first.root_failure_snapshot_id == fixture.failure_snapshot_id
    assert first.autopsy.first_divergence.observable_path == "focus_observation.semantic_pass"
    assert first.autopsy.hypotheses
    assert first.interventions
    assert first.tournament.branches
    assert first.projected_physical_calls == first.tournament.worst_case_physical_calls
    assert first.model_calls == 0
    assert all(request.parent_failure_snapshot_id == fixture.failure_snapshot_id for request in first.replay_requests)
    assert all(request.parent_state_hash == fixture.state_hash for request in first.replay_requests)
    assert not any(isinstance(row, ReplayRequest) for row in replay.records())
    assert replay.registry_path.read_bytes() == before
    assert replay.get_failure(fixture.failure_snapshot_id) == fixture
    assert causal.validate().ok


def test_execute_reuses_replay_executor_and_localizes_target_over_sham(tmp_path):
    lab, fixture, replay, _ = planted_lab(tmp_path)
    program = lab.prepare(fixture.failure_snapshot_id)
    source_before = replay.get_failure(fixture.failure_snapshot_id)

    result = lab.execute(program, adapters={"fake-model": PlantedAdapter()})

    assert result.program == program
    assert result.replay_results
    assert any(item.semantic_pass for item in result.target_results)
    assert result.sham_results and not any(item.semantic_pass for item in result.sham_results)
    assert result.assessment.supported_hypotheses
    assert any(event.to_state is PromotionState.MOVEMENT for event in result.assessment.promotion_events)
    assert not any(
        event.to_state in {PromotionState.TIER_CANDIDATE, PromotionState.CERTIFIED}
        for event in result.assessment.promotion_events
    )
    assert result.child_failure_snapshot_ids
    assert result.model_calls_are_fake_only
    assert replay.get_failure(fixture.failure_snapshot_id) == source_before
    assert any(isinstance(row, MechanismLabel) for row in replay.records())
    assert any(isinstance(row, PromotionEvent) for row in replay.records())
    assert replay.validate().ok


def test_failed_child_can_seed_new_program_without_mutating_parent_evidence(tmp_path):
    lab, fixture, replay, _ = planted_lab(tmp_path)
    program = lab.prepare(fixture.failure_snapshot_id)
    parent_before = replay.get_failure(fixture.failure_snapshot_id)
    result = lab.execute(program, adapters={"fake-model": PlantedAdapter()})
    child_id = result.child_failure_snapshot_ids[0]
    child = replay.get_failure(child_id)

    next_program = lab.ingest_child_failure(child_id)

    assert next_program.failure_snapshot_id == child_id
    assert next_program.root_failure_snapshot_id == fixture.failure_snapshot_id
    assert next_program.autopsy.failure_snapshot_id == child_id
    assert next_program.replay_requests
    assert all(request.parent_failure_snapshot_id == child_id for request in next_program.replay_requests)
    assert all(request.failure_snapshot_id == fixture.failure_snapshot_id for request in next_program.replay_requests)
    assert child.parent_failure_snapshot_id == fixture.failure_snapshot_id
    assert replay.get_failure(fixture.failure_snapshot_id) == parent_before
    assert replay.validate().ok


def test_execute_rejects_program_or_adapter_lineage_drift_before_calls(tmp_path):
    lab, fixture, _, _ = planted_lab(tmp_path)
    program = lab.prepare(fixture.failure_snapshot_id)
    object.__setattr__(program, "failure_snapshot_id", "different-failure")

    class ForbiddenAdapter(PlantedAdapter):
        def execute_fixture(self, fixture, visible_payload, request):
            raise AssertionError("adapter must not be called for a drifted program")

    try:
        lab.execute(program, adapters={"fake-model": ForbiddenAdapter()})
    except ValueError as exc:
        assert "failure" in str(exc).lower() or "lineage" in str(exc).lower()
    else:
        raise AssertionError("drifted research program must be rejected")
