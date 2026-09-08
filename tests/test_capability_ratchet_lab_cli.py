from __future__ import annotations

import json

from inverted.capability_ratchet.cli import main
from inverted.capability_ratchet.core import FailureFixture, Partition, ReplayRequest
from inverted.capability_ratchet.replay_store import ReplayStore


def _store(tmp_path):
    store = ReplayStore(tmp_path / "replay")
    visible = store.put_asset({
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 11, "num_predict": 96},
            "messages": [{"role": "user", "content": "dependency-sensitive task"}],
        }]
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-cli-lab",
        source_campaign_id="campaign-cli",
        source_trial_id="trial-cli",
        focus_observation_id="obs-cli",
        focus_task_id="task-cli",
        batch_task_ids=("task-cli",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0},
        inference_seed=11,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash=visible,
        oracle_ref="oracle:cli",
        expected_contract="plan",
        source_evidence_refs=("source:cli",),
        metadata={"difficulty": 3},
    )
    store.append(fixture)
    return store, store.get_failure(fixture.failure_snapshot_id)


def _call(argv, **kwargs):
    try:
        return main(argv, **kwargs)
    except SystemExit as exc:
        return int(exc.code)


def test_autopsy_cli_is_zero_call_and_replay_immutable(tmp_path, capsys):
    store, fixture = _store(tmp_path)
    before = store.registry_path.read_bytes()
    rc = _call([
        "autopsy",
        "--replay-root", str(store.root),
        "--causal-root", str(tmp_path / "causal"),
        "--snapshot-id", fixture.failure_snapshot_id,
    ])
    payload = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["failure_snapshot_id"] == fixture.failure_snapshot_id
    assert payload["first_divergence"]["observable_path"] == "focus_observation.semantic_pass"
    assert payload["hypotheses"]
    assert store.registry_path.read_bytes() == before
    assert not any(isinstance(row, ReplayRequest) for row in store.records())


def test_plan_and_show_lab_expose_causal_geometry_without_execution(tmp_path, capsys):
    store, fixture = _store(tmp_path)
    causal_root = str(tmp_path / "causal")
    before = store.registry_path.read_bytes()

    assert _call([
        "plan-lab", "--replay-root", str(store.root), "--causal-root", causal_root,
        "--snapshot-id", fixture.failure_snapshot_id,
    ]) == 0
    planned = json.loads(capsys.readouterr().out.strip())
    assert planned["MODEL_CALLS"] == 0
    assert planned["failure_snapshot_id"] == fixture.failure_snapshot_id
    assert planned["hypothesis_ids"]
    assert planned["interventions"]
    assert {row["mode"] for row in planned["branches"]} >= {"TARGET", "SHAM"}
    assert planned["call_geometry"]["minimum"] <= planned["call_geometry"]["expected"] <= planned["call_geometry"]["worst_case"]
    assert planned["replay_request_ids"]
    assert store.registry_path.read_bytes() == before

    assert _call([
        "show-lab", "--replay-root", str(store.root), "--causal-root", causal_root,
        "--snapshot-id", fixture.failure_snapshot_id,
    ]) == 0
    shown = json.loads(capsys.readouterr().out.strip())
    assert shown["MODEL_CALLS"] == 0
    assert shown["failure_snapshot_id"] == fixture.failure_snapshot_id
    assert shown["causal_store_valid"] is True
    assert shown["replay_store_valid"] is True
    assert store.registry_path.read_bytes() == before


def test_run_lab_requires_explicit_gate_before_live_executor(tmp_path, capsys):
    store, fixture = _store(tmp_path)
    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("live lab executor must not be reached without the gate")

    rc = _call([
        "run-lab", "--replay-root", str(store.root),
        "--causal-root", str(tmp_path / "causal"),
        "--snapshot-id", fixture.failure_snapshot_id,
    ], live_lab_executor=forbidden)
    captured = capsys.readouterr()
    assert rc == 2
    assert "--allow-model-calls" in captured.err
    assert called == []


def test_gated_run_lab_enters_injected_executor_without_constructing_default_adapter(tmp_path, capsys):
    store, fixture = _store(tmp_path)
    seen = []

    def fake_live_lab_executor(actual_store, causal_root, args):
        seen.append((actual_store.root, causal_root, args.snapshot_id))
        return {
            "failure_snapshot_id": args.snapshot_id,
            "replay_results": 0,
            "MODEL_CALLS": 0,
        }

    rc = _call([
        "run-lab", "--replay-root", str(store.root),
        "--causal-root", str(tmp_path / "causal"),
        "--snapshot-id", fixture.failure_snapshot_id,
        "--allow-model-calls",
    ], live_lab_executor=fake_live_lab_executor)
    payload = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert payload["MODEL_CALLS"] == 0
    assert seen == [(store.root, tmp_path / "causal", fixture.failure_snapshot_id)]
