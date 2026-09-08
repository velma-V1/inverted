from __future__ import annotations

import json
from dataclasses import replace

import pytest

from inverted.capability_ratchet import (
    FailureFixture, Partition, PromotionState, ReplayMode, ReplayRequest,
)
from inverted.capability_ratchet.cli import main
from inverted.capability_ratchet.query import ReplaySelector, select_failures
from inverted.capability_ratchet.replay_store import ReplayStore


def fixture(store: ReplayStore, *, snapshot: str, model: str, family: str,
            failure: str, campaign: str, partition=Partition.HISTORICAL,
            promotion=PromotionState.UNASSESSED, difficulty=2) -> FailureFixture:
    visible = {"request_envelopes": [{"model": model, "messages": [], "options": {}, "think": False}]}
    asset = store.put_asset(visible)
    item = FailureFixture(
        failure_snapshot_id=snapshot, source_campaign_id=campaign,
        source_trial_id=f"trial-{snapshot}", focus_observation_id=f"obs-{snapshot}",
        focus_task_id=f"task-{snapshot}", batch_task_ids=(f"task-{snapshot}",),
        family=family, failure_classes=(failure,), source_model_id=model,
        source_model_digest=f"digest-{model}", source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0}, inference_seed=1,
        partition=partition, model_visible_asset_sha256=asset, state_hash=asset,
        oracle_ref=f"oracle:{snapshot}", expected_contract="answer_object",
        source_evidence_refs=(f"source:{snapshot}",), promotion_state=promotion,
        metadata={"difficulty": difficulty},
    )
    store.append(item)
    return store.get_failure(snapshot)


def build_store(tmp_path):
    store = ReplayStore(tmp_path / "replay")
    a = fixture(store, snapshot="f-a", model="qwen", family="ARITHMETIC",
                failure="SEMANTIC_FAIL", campaign="c1")
    b = fixture(store, snapshot="f-b", model="qwen", family="PLANNING_DEPENDENCIES",
                failure="REASONING_CAP_EXHAUSTION", campaign="c1",
                promotion=PromotionState.MOVEMENT, difficulty=3)
    c = fixture(store, snapshot="f-c", model="other", family="ARITHMETIC",
                failure="CONTRACT_FAIL", campaign="c2", partition=Partition.DEVELOPMENT,
                difficulty=1)
    request = ReplayRequest(
        replay_request_id="req-x", failure_snapshot_id=a.failure_snapshot_id,
        parent_failure_snapshot_id=a.failure_snapshot_id, parent_state_hash=a.state_hash,
        decision_id="D", hypothesis_id="H", expected_causal_implication="compare target",
        mode=ReplayMode.CROSS_MODEL, source_model_id=a.source_model_id,
        source_model_digest=a.source_model_digest, target_model_id="other",
        target_model_digest="digest-other", partition=a.partition,
        changed_dimensions=("target_model",), overrides={},
    )
    store.append(request)
    return store, (a, b, c)


def test_selector_filters_deterministically_across_supported_dimensions(tmp_path) -> None:
    store, _ = build_store(tmp_path)
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(source_model="qwen")
    )] == ["f-a", "f-b"]
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(family="ARITHMETIC")
    )] == ["f-a", "f-c"]
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(failure_class="REASONING_CAP_EXHAUSTION")
    )] == ["f-b"]
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(campaign="c2", partition=Partition.DEVELOPMENT)
    )] == ["f-c"]
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(promotion_state=PromotionState.MOVEMENT)
    )] == ["f-b"]
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(snapshot_ids=("f-c", "f-a"))
    )] == ["f-a", "f-c"]


def test_target_model_filter_uses_replay_activity_without_mutating_source(tmp_path) -> None:
    store, fixtures = build_store(tmp_path)
    selected = select_failures(store, ReplaySelector(target_model="other"))
    assert [f.failure_snapshot_id for f in selected] == ["f-a"]
    assert store.get_failure("f-a") == fixtures[0]


def test_cli_list_show_validate_and_plan_are_inspection_only(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    root = str(store.root)
    assert main(["validate", "--replay-root", root]) == 0
    validate_out = json.loads(capsys.readouterr().out.strip())
    assert validate_out["ok"] is True and validate_out["MODEL_CALLS"] == 0

    assert main(["list", "--replay-root", root, "--source-model", "qwen"]) == 0
    listed = json.loads(capsys.readouterr().out.strip())
    assert [row["failure_snapshot_id"] for row in listed["failures"]] == ["f-a", "f-b"]

    assert main(["show", "--replay-root", root, "--snapshot-id", "f-a"]) == 0
    shown = json.loads(capsys.readouterr().out.strip())
    assert shown["fixture"]["failure_snapshot_id"] == "f-a"
    assert "request_envelopes" in shown["visible_asset"]

    assert main(["plan-replay", "--replay-root", root, "--source-model", "qwen",
                 "--family", "ARITHMETIC", "--limit", "1"]) == 0
    planned = json.loads(capsys.readouterr().out.strip())
    assert planned["MODEL_CALLS"] == 0
    assert planned["plans"][0]["projected_physical_calls"] == 1


def test_execute_replay_requires_explicit_model_call_gate_before_adapter_import(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    rc = main(["execute-replay", "--replay-root", str(store.root), "--snapshot-id", "f-a"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "--allow-model-calls" in captured.err


def test_cross_model_plan_requires_explicit_target_digest(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    rc = main([
        "plan-replay", "--replay-root", str(store.root),
        "--source-model", "qwen", "--target-model", "other", "--limit", "1",
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "target digest" in captured.err.lower()


def test_same_model_plan_rejects_conflicting_target_digest(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    rc = main([
        "plan-replay", "--replay-root", str(store.root), "--snapshot-id", "f-a",
        "--target-digest", "wrong-digest",
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "digest" in captured.err.lower()


def test_show_missing_snapshot_fails_cleanly(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    rc = main(["show", "--replay-root", str(store.root), "--snapshot-id", "missing"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "missing" in captured.err.lower()


def test_allow_gate_enters_injected_live_executor_without_real_model_calls(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    before = store.registry_path.read_bytes()
    seen = []
    def fake_live_executor(actual_store, args):
        seen.append((actual_store.root, args.snapshot_id))
        return {"replay_result_id": "fake-result", "MODEL_CALLS": 0}
    rc = main([
        "execute-replay", "--replay-root", str(store.root),
        "--snapshot-id", "f-a", "--allow-model-calls",
    ], live_executor=fake_live_executor)
    payload = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and payload["MODEL_CALLS"] == 0
    assert seen == [(store.root, "f-a")]
    assert store.registry_path.read_bytes() == before


def test_plan_target_model_is_not_used_as_prior_activity_filter(tmp_path, capsys) -> None:
    store, _ = build_store(tmp_path)
    rc = main([
        "plan-replay", "--replay-root", str(store.root),
        "--source-model", "qwen", "--family", "PLANNING_DEPENDENCIES",
        "--target-model", "brand-new-model", "--target-digest", "brand-new-digest",
        "--limit", "1",
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert len(payload["plans"]) == 1
    assert payload["plans"][0]["failure_snapshot_id"] == "f-b"
    assert payload["plans"][0]["target_model"] == "brand-new-model"


def test_unique_fixture_selection_does_not_rescan_registry_per_fixture(tmp_path, monkeypatch) -> None:
    store, _ = build_store(tmp_path)

    def forbidden_get_failure(*args, **kwargs):
        raise AssertionError("unique fixture selection must resolve from one registry read")

    monkeypatch.setattr(store, "get_failure", forbidden_get_failure)
    selected = select_failures(store, ReplaySelector())
    assert [f.failure_snapshot_id for f in selected] == ["f-a", "f-b", "f-c"]


def test_selector_filters_by_collected_difficulty(tmp_path) -> None:
    store, _ = build_store(tmp_path)
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(difficulty=3)
    )] == ["f-b"]
    assert [f.failure_snapshot_id for f in select_failures(
        store, ReplaySelector(difficulty=1)
    )] == ["f-c"]


def _build_mutation_cli_state(tmp_path):
    from inverted.capability_ratchet.causal_core import MechanismRole
    from inverted.capability_ratchet.causal_store import CausalEvidenceStore
    from inverted.capability_ratchet.core import (
        MechanismLabel, MutationFixture, PromotionEvent, ReplayResult,
    )
    from inverted.capability_ratchet.mutation_core import (
        MutationAxis, MutationDirection, MutationOrigin, MutationPolicy, MutationSpec,
    )
    from inverted.capability_ratchet.mutation_store import MutationEvidenceStore, MutationStudy
    from inverted.capability_ratchet.surface_store import SurfaceEvidenceStore

    replay = ReplayStore(tmp_path / "mutation-cli-replay")
    visible = {
        "request_envelopes": [{
            "model": "fake-model", "stream": False, "think": False,
            "options": {"seed": 1},
            "messages": [{"role": "user", "content": "BASE"}],
        }],
        "task": {"depth": 2},
    }
    source = FailureFixture(
        failure_snapshot_id="mutation-cli-root",
        source_campaign_id="campaign", source_trial_id="trial",
        focus_observation_id="obs", focus_task_id="task", batch_task_ids=("task",),
        family="PLANNING", failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model", source_model_digest="fake-digest",
        source_runtime={"provider": "fake"}, inference_profile={"thinking_budget": 0},
        inference_seed=1, partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=replay.put_asset(visible), state_hash="a" * 64,
        oracle_ref="oracle", expected_contract="answer", source_evidence_refs=("source:1",),
        oracle_asset_sha256=replay.put_asset({"answer": "base"}),
    )
    replay.append(source)
    source = replay.get_failure(source.failure_snapshot_id)
    request = ReplayRequest(
        replay_request_id="mutation-cli-movement-request",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        decision_id="D4", hypothesis_id="hyp-cli",
        expected_causal_implication="repair works", mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=source.source_model_id, source_model_digest=source.source_model_digest,
        target_model_id=source.source_model_id, target_model_digest=source.source_model_digest,
        partition=source.partition,
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        intervention_id="int-cli",
        overrides={"request_envelopes.0.messages.0.content": "REPAIRED"},
    )
    replay.append(request)
    result = ReplayResult(
        replay_result_id="mutation-cli-movement-result",
        replay_request_id=request.replay_request_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash, mode=request.mode,
        target_model_id=source.source_model_id, target_model_digest=source.source_model_digest,
        partition=source.partition, completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=replay.put_asset({"ok": True}),
        raw_call_asset_sha256=replay.put_asset({"raw_calls": [{"request": visible["request_envelopes"][0]}]}),
    )
    replay.append(result)
    label = MechanismLabel(
        mechanism_label_id="mutation-cli-label",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="mutation-cli-mechanism", hypothesis_id="hyp-cli",
        intervention_ids=("int-cli",), role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(result.replay_result_id,), confidence=1.0,
    )
    replay.append(label)
    replay.append(PromotionEvent(
        promotion_event_id="mutation-cli-movement",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=label.mechanism_id,
        from_state=PromotionState.UNASSESSED, to_state=PromotionState.MOVEMENT,
        reason="movement", evidence_replay_result_ids=(result.replay_result_id,),
        partition=source.partition,
    ))

    causal = CausalEvidenceStore(tmp_path / "mutation-cli-causal", replay_store=replay)
    surface = SurfaceEvidenceStore(
        tmp_path / "mutation-cli-surface", replay_store=replay, causal_store=causal
    )
    mutation = MutationEvidenceStore(
        tmp_path / "mutation-cli-mutation", replay_store=replay, surface_store=surface
    )
    spec = MutationSpec(
        axis=MutationAxis.DEPENDENCY_DEPTH,
        direction=MutationDirection.HARDER,
        value=5,
        structural_region_id="planning/dependency",
        protected=True,
    )
    study = MutationStudy(
        study_id="mutation-cli-study",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=label.mechanism_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        operating_surface_profile_id=None,
        policy=MutationPolicy(), decision_id="D12",
        candidate_specs=(spec,), protected_spec_ids=(spec.spec_id,),
    )
    mutation.append_study(study)
    fixture_row = MutationFixture.create(
        failure_snapshot_id=source.failure_snapshot_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        mechanism_id=label.mechanism_id,
        mutation_axis=spec.axis, mutation_direction=spec.direction,
        mutation_value=spec.value, structural_region_id=spec.structural_region_id,
        model_visible_asset_sha256=replay.put_asset({**visible, "task": {"depth": 5}}),
        oracle_asset_sha256=replay.put_asset({"answer": "mutated"}),
        semantic_contract_hash="d" * 64, partition=source.partition,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
        metadata={
            "mutation_spec_id": spec.spec_id,
            "protected": True,
            "operating_surface_profile_id": "movement-only",
        },
    )
    replay.append(fixture_row)
    assert replay.validate().ok and mutation.validate().ok
    return replay, causal, surface, mutation, study


def test_mutation_plan_and_show_cli_are_zero_call_inspection_paths(tmp_path, capsys) -> None:
    replay, causal, surface, mutation, study = _build_mutation_cli_state(tmp_path)
    common = [
        "--replay-root", str(replay.root),
        "--causal-root", str(causal.root),
        "--surface-root", str(surface.root),
        "--mutation-root", str(mutation.root),
        "--study-id", study.study_id,
    ]
    assert main(["plan-mutations", *common]) == 0
    planned = json.loads(capsys.readouterr().out.strip())
    assert planned["MODEL_CALLS"] == 0
    assert planned["study_id"] == study.study_id
    assert len(planned["specs"]) == 1

    assert main(["show-mutations", *common]) == 0
    shown = json.loads(capsys.readouterr().out.strip())
    assert shown["MODEL_CALLS"] == 0
    assert shown["study"]["study_id"] == study.study_id
    assert shown["mutation_store_valid"] is True


def test_run_mutations_gate_fires_before_any_store_or_adapter_construction(tmp_path, capsys) -> None:
    rc = main([
        "run-mutations",
        "--replay-root", str(tmp_path / "missing-replay"),
        "--causal-root", str(tmp_path / "missing-causal"),
        "--surface-root", str(tmp_path / "missing-surface"),
        "--mutation-root", str(tmp_path / "missing-mutation"),
        "--study-id", "missing-study",
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "--allow-model-calls" in captured.err


def test_run_mutations_allow_gate_enters_injected_executor_without_real_calls(tmp_path, capsys) -> None:
    replay, causal, surface, mutation, study = _build_mutation_cli_state(tmp_path)
    seen = []

    def fake_runner(actual_store, causal_root, surface_root, mutation_root, args):
        seen.append((actual_store.root, causal_root, surface_root, mutation_root, args.study_id))
        return {"study_id": args.study_id, "MODEL_CALLS": 0}

    rc = main([
        "run-mutations",
        "--replay-root", str(replay.root),
        "--causal-root", str(causal.root),
        "--surface-root", str(surface.root),
        "--mutation-root", str(mutation.root),
        "--study-id", study.study_id,
        "--allow-model-calls",
    ], live_mutation_executor=fake_runner)
    payload = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and payload["MODEL_CALLS"] == 0
    assert seen == [(replay.root, causal.root, surface.root, mutation.root, study.study_id)]
