from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    MechanismRole,
)
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
from inverted.capability_ratchet.replay_store import ReplayStore
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
from inverted.capability_ratchet.surface_store import SurfaceEvidenceStore


STATE_HASH = "1" * 64
MECHANISM_ID = "mechanism-surface"


def _seed_lineage(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({"request_envelopes": [{"model": "model", "messages": []}]})
    output = replay.put_asset({"output": "ok"})
    raw = replay.put_asset({"request": {}, "response": {}})
    fixture = FailureFixture(
        failure_snapshot_id="failure-surface",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="model",
        source_model_digest="digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking": False, "thinking_budget": 0, "temperature": 0.7},
        inference_seed=1,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash=STATE_HASH,
        oracle_ref="oracle",
        expected_contract="answer",
        source_evidence_refs=("raw:1",),
    )
    replay.append(fixture)

    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.INSUFFICIENT_REASONING,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=("forensic:focus_observation",),
            confidence=0.9,
        ),
        owner_candidate=ArchitectureOwner.MODEL,
        claim="bounded additional reasoning repairs the same failure state",
        expected_if_true="a bounded cognition intervention passes while control remains failed",
        falsifier="bounded cognition does not improve the same state",
    )
    causal.append_hypothesis(hypothesis)

    request = ReplayRequest.for_exact(
        fixture,
        decision_id="D3",
        hypothesis_id=hypothesis.hypothesis_id,
        request_id="surface-existing-request",
    )
    replay.append(request)
    result = ReplayResult(
        replay_result_id="surface-existing-result",
        replay_request_id=request.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        mode=request.mode,
        target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest,
        partition=fixture.partition,
        completed=True,
        semantic_pass=True,
        contract_pass=True,
        output_asset_sha256=output,
        raw_call_asset_sha256=raw,
        metrics={"physical_calls": 1, "thinking_tokens": 0},
    )
    replay.append(result)
    label = MechanismLabel(
        mechanism_label_id="mechanism-label-surface",
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        mechanism_id=MECHANISM_ID,
        hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=("intervention-surface",),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(result.replay_result_id,),
        confidence=0.9,
    )
    replay.append(label)
    replay.append(PromotionEvent(
        promotion_event_id="promotion-surface",
        failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id=MECHANISM_ID,
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="same-state treatment beat control",
        evidence_replay_result_ids=(result.replay_result_id,),
        partition=fixture.partition,
    ))
    assert replay.validate().ok
    assert causal.validate().ok

    study = SurfaceStudy.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id=MECHANISM_ID,
        parent_state_hash=fixture.state_hash,
        partition=fixture.partition,
        promotion_state=PromotionState.MOVEMENT,
        decision_id="D3",
        axes=(SurfaceAxis.REASONING_BUDGET,),
        axis_values={"REASONING_BUDGET": (0, 512, 1024, 2048)},
    )
    point = SurfacePoint.create(
        study=study,
        axis=SurfaceAxis.REASONING_BUDGET,
        value=512,
        decision_id="D3",
    )
    return replay, causal, study, point, result


def _profile(study: SurfaceStudy, observation_id: str) -> OperatingSurfaceProfile:
    return OperatingSurfaceProfile.create(
        study=study,
        band=SurfaceBand(
            axis=SurfaceAxis.REASONING_BUDGET,
            disposition=SurfaceDisposition.USEFUL_BAND,
            lower_useful=512,
            upper_useful=2048,
            recommended_region=(512, 1024, 2048),
            harm_onset=None,
            evidence_observation_ids=(observation_id,),
        ),
        evidence_refs=(observation_id,),
        call_geometry=SurfaceCallGeometry(0, 0, 0, 0),
    )


def test_surface_store_is_append_only_idempotent_and_cross_store_validated(tmp_path) -> None:
    replay, causal, study, point, result = _seed_lineage(tmp_path)
    store = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)

    assert store.append_study(study) == study.study_id
    before = store.study_path.read_bytes()
    assert store.append_study(study) == study.study_id
    assert store.study_path.read_bytes() == before

    causal_observation = SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
        replay_result_ids=(result.replay_result_id,),
        metrics={"semantic_pass": True, "contract_pass": True, "physical_calls": 1},
    )
    prior = SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.HISTORICAL_PRIOR,
        source_evidence_refs=("v2:atomic-observations:12",),
        metrics={"semantic_pass": True, "thinking_tokens": 510},
    )
    assert store.append_observation(causal_observation) == causal_observation.observation_id
    assert store.append_observation(prior) == prior.observation_id
    profile = _profile(study, causal_observation.observation_id)
    assert store.append_profile(profile) == profile.profile_id

    assert store.studies() == (study,)
    assert store.observations(study.study_id) == (causal_observation, prior)
    assert store.profiles(study.mechanism_id) == (profile,)
    report = store.validate()
    assert report.ok
    assert report.study_count == 1
    assert report.observation_count == 2
    assert report.profile_count == 1


def test_surface_store_rejects_forged_movement_and_unknown_replay_result(tmp_path) -> None:
    replay, causal, study, point, _ = _seed_lineage(tmp_path)
    store = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    forged = replace(study, mechanism_id="mechanism-does-not-exist")
    with pytest.raises(ValueError, match="MOVEMENT|mechanism"):
        store.append_study(forged)

    store.append_study(study)
    unknown = SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
        replay_result_ids=("missing-replay-result",),
        metrics={"semantic_pass": True},
    )
    with pytest.raises(ValueError, match="replay result"):
        store.append_observation(unknown)


def test_surface_store_rejects_logical_id_rewrite_and_unresolved_profile_refs(tmp_path) -> None:
    replay, causal, study, _, _ = _seed_lineage(tmp_path)
    store = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    store.append_study(study)

    with pytest.raises(ValueError, match="different canonical content"):
        store.append_study(replace(study, decision_id="D4"))

    with pytest.raises(ValueError, match="observation"):
        store.append_profile(_profile(study, "missing-observation"))


def test_surface_store_detects_manifest_tamper(tmp_path) -> None:
    replay, causal, study, _, _ = _seed_lineage(tmp_path)
    store = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    store.append_study(study)
    assert store.validate().ok

    store.study_manifest_path.write_text("0" * 64 + "\n", encoding="ascii")
    report = store.validate()
    assert not report.ok
    assert "surface-studies.sha256" in report.hash_mismatches

    store.study_manifest_path.write_bytes(
        hashlib.sha256(store.study_path.read_bytes()).hexdigest().encode("ascii") + b"\n"
    )
    assert store.validate().ok
