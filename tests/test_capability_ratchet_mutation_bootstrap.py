from __future__ import annotations

from types import SimpleNamespace

from inverted.capability_ratchet.causal_core import MechanismRole
from inverted.capability_ratchet.core import (
    FailureFixture,
    MechanismLabel,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.mutation_bootstrap import plan_eligible_mutations
from inverted.capability_ratchet.mutation_store import MutationEvidenceStore
from inverted.capability_ratchet.replay_store import ReplayStore


class SurfaceStub:
    def profiles(self, mechanism_id=None):
        return ()

    def validate(self):
        return SimpleNamespace(ok=True)


def _store(tmp_path) -> tuple[ReplayStore, MutationEvidenceStore]:
    replay = ReplayStore(tmp_path / "replay")
    mutation = MutationEvidenceStore(
        tmp_path / "mutation",
        replay_store=replay,
        surface_store=SurfaceStub(),
    )
    return replay, mutation


def _movement(replay: ReplayStore) -> tuple[FailureFixture, MechanismLabel]:
    visible_sha = replay.put_asset(
        {"request_envelopes": [{"model": "fake-model", "messages": []}]}
    )
    source = FailureFixture(
        failure_snapshot_id="failure-stage6-bootstrap",
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
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible_sha,
        state_hash="a" * 64,
        oracle_ref="oracle",
        expected_contract="answer",
        source_evidence_refs=("source:bootstrap",),
    )
    replay.append(source)
    request = ReplayRequest(
        replay_request_id="bootstrap-repair-request",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        decision_id="D4",
        hypothesis_id="hypothesis-bootstrap",
        expected_causal_implication="repair succeeds",
        mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=source.source_model_id,
        source_model_digest=source.source_model_digest,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        changed_dimensions=("repair",),
        intervention_id="intervention-bootstrap",
        overrides={"repair": True},
    )
    replay.append(request)
    result = ReplayResult(
        replay_result_id="bootstrap-repair-result",
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
        output_asset_sha256=replay.put_asset({"passed": True}),
        raw_call_asset_sha256=replay.put_asset({"raw_calls": []}),
    )
    replay.append(result)
    mechanism = MechanismLabel(
        mechanism_label_id="bootstrap-mechanism-label",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="bootstrap-mechanism",
        hypothesis_id="hypothesis-bootstrap",
        intervention_ids=("intervention-bootstrap",),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(result.replay_result_id,),
        confidence=1.0,
    )
    replay.append(mechanism)
    replay.append(
        PromotionEvent(
            promotion_event_id="bootstrap-movement-event",
            failure_snapshot_id=source.failure_snapshot_id,
            mechanism_id=mechanism.mechanism_id,
            from_state=PromotionState.UNASSESSED,
            to_state=PromotionState.MOVEMENT,
            reason="planted movement",
            evidence_replay_result_ids=(result.replay_result_id,),
            partition=source.partition,
        )
    )
    assert replay.validate().ok
    return source, mechanism


def test_zero_call_bootstrap_reports_no_eligible_mechanisms_without_movement(tmp_path) -> None:
    _replay, mutation = _store(tmp_path)

    result = plan_eligible_mutations(mutation)

    assert result.status == "NO_ELIGIBLE_MECHANISMS"
    assert result.eligible_mechanisms == ()
    assert result.plans == ()
    assert result.model_calls == 0


def test_zero_call_bootstrap_reports_no_mutation_template_for_movement_without_stage6_study(tmp_path) -> None:
    replay, mutation = _store(tmp_path)
    _source, mechanism = _movement(replay)

    result = plan_eligible_mutations(mutation)

    assert result.status == "NO_MUTATION_TEMPLATE"
    assert result.eligible_mechanisms == (mechanism.mechanism_id,)
    assert result.plans == ()
    assert result.model_calls == 0
