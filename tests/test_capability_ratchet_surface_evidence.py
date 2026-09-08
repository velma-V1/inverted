from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.historical import V2EvidenceSource
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.surface_core import (
    SurfaceAxis,
    SurfaceEvidenceKind,
    SurfacePoint,
    SurfaceStudy,
)
from inverted.capability_ratchet.surface_evidence import SurfaceEvidenceCompiler
from inverted.capability_ratchet.surface_store import SurfaceEvidenceStore


STATE_HASH = "2" * 64
MECHANISM_ID = "mechanism-reasoning"


def _seed_surface(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({"request_envelopes": [{"model": "model", "messages": [], "think": False,
                                                       "options": {"num_predict": 768, "temperature": 0.7}}]})
    output = replay.put_asset({"output": "ok"})
    raw = replay.put_asset({"request": {}, "response": {}})
    fixture = FailureFixture(
        failure_snapshot_id="failure-reasoning", source_campaign_id="campaign", source_trial_id="trial",
        focus_observation_id="obs", focus_task_id="task", batch_task_ids=("task",), family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="model", source_model_digest="digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking": False, "thinking_budget": 0, "temperature": 0.7},
        inference_seed=7, partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible, state_hash=STATE_HASH,
        oracle_ref="oracle", expected_contract="answer", source_evidence_refs=("raw:1",),
    )
    replay.append(fixture)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.INSUFFICIENT_REASONING,
            observable_path="focus_observation.semantic_pass", event_index=0,
            evidence_refs=("forensic:focus",), confidence=0.9,
        ), owner_candidate=ArchitectureOwner.MODEL,
        claim="more bounded reasoning repairs this state",
        expected_if_true="bounded reasoning passes", falsifier="bounded reasoning fails",
    )
    causal.append_hypothesis(hypothesis)

    exact = ReplayRequest.for_exact(
        fixture, decision_id="D3", hypothesis_id=hypothesis.hypothesis_id, request_id="exact-baseline"
    )
    replay.append(exact)
    exact_result = ReplayResult(
        replay_result_id="result-baseline", replay_request_id=exact.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
        mode=exact.mode, target_model_id=fixture.source_model_id, target_model_digest=fixture.source_model_digest,
        partition=fixture.partition, completed=True, semantic_pass=False, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
        failure_classes=("SEMANTIC_FAIL",), child_failure_snapshot_id="child-baseline",
        metrics={"physical_calls": 1, "thinking_tokens": 0},
    )
    child = FailureFixture(
        failure_snapshot_id="child-baseline", source_campaign_id="campaign", source_trial_id="trial-child",
        focus_observation_id="obs-child", focus_task_id="task", batch_task_ids=("task",), family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="model", source_model_digest="digest",
        source_runtime={"provider": "fake"}, inference_profile=fixture.inference_profile, inference_seed=7,
        partition=fixture.partition, model_visible_asset_sha256=visible, state_hash="3" * 64,
        oracle_ref="oracle", expected_contract="answer", source_evidence_refs=("raw:child",),
        parent_failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
    )
    replay.append(child)
    replay.append(exact_result)

    budget_dimension = "request_envelopes.0.options.num_predict"
    counterfactual = ReplayRequest(
        replay_request_id="budget-1024", failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
        decision_id="D3", hypothesis_id=hypothesis.hypothesis_id,
        expected_causal_implication="test a 1024-token reasoning budget",
        mode=ReplayMode.COUNTERFACTUAL, source_model_id=fixture.source_model_id,
        source_model_digest=fixture.source_model_digest, target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest, partition=fixture.partition,
        changed_dimensions=(budget_dimension,), overrides={budget_dimension: 1024},
    )
    replay.append(counterfactual)
    replay.append(ReplayResult(
        replay_result_id="result-budget-1024", replay_request_id=counterfactual.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
        mode=counterfactual.mode, target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest, partition=fixture.partition,
        completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
        metrics={"physical_calls": 2, "thinking_tokens": 900},
    ))
    label = MechanismLabel(
        mechanism_label_id="label-reasoning", failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
        mechanism_id=MECHANISM_ID, hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=(counterfactual.intervention_id,), role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=("result-budget-1024",), confidence=0.9,
    )
    replay.append(label)
    replay.append(PromotionEvent(
        promotion_event_id="promotion-reasoning", failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id=MECHANISM_ID, from_state=PromotionState.UNASSESSED, to_state=PromotionState.MOVEMENT,
        reason="bounded reasoning beat baseline", evidence_replay_result_ids=("result-budget-1024",),
        partition=fixture.partition,
    ))
    assert replay.validate().ok

    study = SurfaceStudy.create(
        failure_snapshot_id=fixture.failure_snapshot_id, mechanism_id=MECHANISM_ID,
        parent_state_hash=fixture.state_hash, partition=fixture.partition,
        promotion_state=PromotionState.MOVEMENT, decision_id="D3",
        axes=(SurfaceAxis.REASONING_BUDGET,),
        axis_values={"REASONING_BUDGET": (0, 512, 1024, 2048)},
    )
    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    surface.append_study(study)
    return replay, causal, surface, study


def _write_mini_v2(root: Path, *, budget: int = 1024, temperature: float = 1.0) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tasks = [{
        "task_id": f"mini-{index}", "family": "ARITHMETIC", "difficulty": 2,
        "prompt": f"Compute {index}+1", "expected": index + 1,
        "scorer": "exact_value", "contract": "answer_object", "metadata": [],
    } for index in range(5)]
    pool = {"protocol_version": 2, "seed": 17, "tasks": tasks}
    (root / "task-pool-v2.json").write_text(json.dumps(pool) + "\n", encoding="utf-8")
    canonical = json.dumps(pool, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    manifest = {
        "protocol_version": 2, "task_pool_sha256": hashlib.sha256(canonical).hexdigest(),
        "runtime_provenance": {"provider": "ollama", "model": "qwen", "model_digest": "digest-v2"},
    }
    (root / "protocol-v2-manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    raw = {
        "trial_id": "trial-v2", "physical_calls": 2,
        "raw_calls": [{"request": {"think": True, "options": {"num_predict": budget, "temperature": temperature}},
                       "response": {"done_reason": "length", "eval_count": budget}} ,
                      {"request": {"think": False}, "response": {"done_reason": "stop", "eval_count": 20}}],
    }
    (root / "raw_calls.jsonl").write_text(json.dumps(raw) + "\n", encoding="utf-8")
    rows = []
    for index, task in enumerate(tasks):
        rows.append({
            "observation_id": f"v2-obs-{index}", "batch_id": "ARITHMETIC:budget:000",
            "task_id": task["task_id"], "family": "ARITHMETIC", "stage": "budget",
            "profile": {"thinking_budget": budget, "temperature": temperature, "top_p": None,
                        "top_k": None, "min_p": None, "presence_penalty": None, "repeat_penalty": None},
            "inference_seed": 91, "decision_reason": "V2_BUDGET",
            "semantic_pass": index != 0, "contract_pass": True, "completed": True,
            "semantic_quality": 0.0 if index == 0 else 1.0, "contract_quality": 1.0,
            "latency_s": 0.2, "output_tokens": 20, "thinking_tokens": budget,
            "physical_calls": 2, "response_text": "x", "failure_classes": [],
            "raw_call_refs": ("trial-v2:call:0",), "metadata": (("trial_id", "trial-v2"),),
        })
    (root / "atomic_observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return root


def test_same_state_exact_and_counterfactual_replays_are_reused_as_answered_points(tmp_path) -> None:
    replay, causal, surface, study = _seed_surface(tmp_path)
    compiler = SurfaceEvidenceCompiler(replay, causal, surface)
    rows = compiler.same_state_observations(study)
    assert {row.value for row in rows} == {0, 1024}
    assert all(row.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL for row in rows)
    assert all(row.metrics["MODEL_CALLS"] == 0 for row in rows)

    answered = compiler.answered_points(study)
    expected = {
        SurfacePoint.create(study=study, axis=SurfaceAxis.REASONING_BUDGET, value=value, decision_id="D3").surface_point_id
        for value in (0, 1024)
    }
    assert answered == expected


def test_historical_v2_prior_orders_budget_evidence_but_cannot_answer_same_state_point(tmp_path) -> None:
    replay, causal, surface, study = _seed_surface(tmp_path)
    compiler = SurfaceEvidenceCompiler(replay, causal, surface)
    source = V2EvidenceSource(_write_mini_v2(tmp_path / "v2", budget=512))
    priors = compiler.compile_v2_priors(source, study)
    assert len(priors) == 5
    assert all(row.evidence_kind is SurfaceEvidenceKind.HISTORICAL_PRIOR for row in priors)
    assert all(row.value == 512 for row in priors)
    assert all(row.metrics["reasoning_cap_exhausted"] is True for row in priors)
    assert all(row.metrics["MODEL_CALLS"] == 0 for row in priors)
    point_512 = SurfacePoint.create(study=study, axis=SurfaceAxis.REASONING_BUDGET, value=512, decision_id="D3")
    assert point_512.surface_point_id not in compiler.answered_points(study)


def test_prior_outside_registered_surface_or_wrong_family_is_not_imported(tmp_path) -> None:
    replay, causal, surface, study = _seed_surface(tmp_path)
    compiler = SurfaceEvidenceCompiler(replay, causal, surface)
    outside = V2EvidenceSource(_write_mini_v2(tmp_path / "outside", budget=8192))
    assert compiler.compile_v2_priors(outside, study) == ()


def test_compilation_is_idempotent_and_never_invokes_model_transport(tmp_path, monkeypatch) -> None:
    replay, causal, surface, study = _seed_surface(tmp_path)
    compiler = SurfaceEvidenceCompiler(replay, causal, surface)
    source = V2EvidenceSource(_write_mini_v2(tmp_path / "v2", budget=512))
    monkeypatch.setattr(
        "inverted.universal_tuning.qwen_ollama.QwenOllamaAdapter._post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model transport forbidden")),
    )
    first = compiler.compile_v2_priors(source, study)
    before = surface.observation_path.read_bytes()
    second = compiler.compile_v2_priors(source, study)
    assert second == first
    assert surface.observation_path.read_bytes() == before
