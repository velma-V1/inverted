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
