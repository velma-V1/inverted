from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from inverted.capability_ratchet import FailureFixture, Partition, ReplayMode, ReplayRequest, ReplayResult
from inverted.capability_ratchet.replay_store import ReplayStore


def fixture(asset: str, **changes: object) -> FailureFixture:
    values = dict(
        failure_snapshot_id="fail-1", source_campaign_id="campaign", source_trial_id="trial",
        focus_observation_id="obs", focus_task_id="task", batch_task_ids=("task",), family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="model", source_model_digest="digest",
        source_runtime={"provider": "fake"}, inference_profile={"temperature": 0}, inference_seed=1,
        partition=Partition.DEVELOPMENT, model_visible_asset_sha256=asset, state_hash="1" * 64,
        oracle_ref="oracle", expected_contract="answer", source_evidence_refs=("raw:1",),
    )
    values.update(changes)
    return FailureFixture(**values)  # type: ignore[arg-type]


def test_canonical_durable_append_assets_idempotence_and_manifest(tmp_path, monkeypatch) -> None:
    store = ReplayStore(tmp_path)
    calls: list[int] = []
    monkeypatch.setattr("inverted.capability_ratchet.replay_store.os.fsync", calls.append)
    digest = store.put_asset({"unicode": "café", "a": [2, 1]})
    assert store.put_asset({"a": [2, 1], "unicode": "café"}) == digest
    assert store.read_asset(digest) == {"a": [2, 1], "unicode": "café"}
    record_id = store.append(fixture(digest))
    assert store.append(fixture(digest)) == record_id
    rows = (tmp_path / "TEST_REPLAY.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert rows[0] == json.dumps(json.loads(rows[0]), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert json.loads(rows[0])["record_id"] == record_id
    assert calls
    manifest = (tmp_path / "TEST_REPLAY.sha256").read_text(encoding="ascii").strip()
    assert manifest == hashlib.sha256((tmp_path / "TEST_REPLAY.jsonl").read_bytes()).hexdigest()
    assert store.validate().ok


def test_append_only_supersession_and_registry_tamper(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    old = store.append(fixture(asset))
    new = store.append(fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2"))
    link = store.supersede(old, new, "corrected observation identity")
    assert link and len(store.records()) == 3
    before = (tmp_path / "TEST_REPLAY.jsonl").read_bytes()
    assert store.supersede(old, new, "corrected observation identity") == link
    assert (tmp_path / "TEST_REPLAY.jsonl").read_bytes() == before
    with (tmp_path / "TEST_REPLAY.jsonl").open("ab") as handle:
        handle.write(b" ")
    report = store.validate()
    assert not report.ok and "TEST_REPLAY.sha256" in report.hash_mismatches


def test_asset_missing_and_tamper_are_detected(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    digest = store.put_asset({"visible": True})
    store.append(fixture(digest))
    path = tmp_path / "replay-assets" / "sha256" / f"{digest}.json"
    path.write_text("{}", encoding="utf-8")
    assert digest in store.validate().hash_mismatches
    path.unlink()
    assert digest in store.validate().missing_assets


def test_cross_record_lineage_is_fully_validated(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    visible = store.put_asset({"request": 1})
    output = store.put_asset({"output": 1})
    raw = store.put_asset({"raw": 1})
    root = fixture(visible)
    store.append(root)
    parent = fixture(
        visible,
        failure_snapshot_id="fail-parent",
        focus_observation_id="obs-parent",
        parent_failure_snapshot_id=root.failure_snapshot_id,
        parent_state_hash=root.state_hash,
        state_hash="2" * 64,
    )
    store.append(parent)
    request = ReplayRequest(
        replay_request_id="req-1", failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=parent.failure_snapshot_id, parent_state_hash=parent.state_hash,
        decision_id="D1", hypothesis_id="H1", expected_causal_implication="reproduce branch",
        mode=ReplayMode.EXACT, source_model_id=parent.source_model_id,
        source_model_digest=parent.source_model_digest, target_model_id=parent.source_model_id,
        target_model_digest=parent.source_model_digest, partition=parent.partition,
    )
    store.append(request)
    child = fixture(visible, failure_snapshot_id="fail-child", focus_observation_id="obs-child",
                    parent_failure_snapshot_id=parent.failure_snapshot_id, parent_state_hash=parent.state_hash,
                    state_hash="3" * 64)
    store.append(child)
    result = ReplayResult(
        replay_result_id="result-1", replay_request_id="req-1",
        failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=parent.failure_snapshot_id,
        parent_state_hash=parent.state_hash, mode=ReplayMode.EXACT, target_model_id="model",
        target_model_digest="digest", partition=Partition.DEVELOPMENT, completed=True,
        semantic_pass=False, contract_pass=True, output_asset_sha256=output, raw_call_asset_sha256=raw,
        failure_classes=("SEMANTIC_FAIL",), child_failure_snapshot_id="fail-child",
    )
    store.append(result)
    assert store.validate().ok

    bad = replace(result, replay_result_id="result-bad", target_model_id="wrong")
    store.append(bad)
    report = store.validate()
    assert not report.ok
    assert any("result-bad" in item and "target model" in item for item in report.broken_lineage)


def test_root_failure_lineage_is_required_and_must_match_parent_family(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"x": 1})
    root = fixture(asset)
    other_root = fixture(asset, failure_snapshot_id="fail-other", focus_observation_id="obs-other")
    parent = fixture(
        asset, failure_snapshot_id="fail-parent", focus_observation_id="obs-parent",
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        state_hash="2" * 64,
    )
    for record in (root, other_root, parent):
        store.append(record)

    wrong_family = ReplayRequest(
        replay_request_id="wrong-family", failure_snapshot_id=other_root.failure_snapshot_id,
        parent_failure_snapshot_id=parent.failure_snapshot_id, parent_state_hash=parent.state_hash,
        decision_id="D", hypothesis_id="H", expected_causal_implication="invalid root family",
        mode=ReplayMode.EXACT, source_model_id=parent.source_model_id,
        source_model_digest=parent.source_model_digest, target_model_id=parent.source_model_id,
        target_model_digest=parent.source_model_digest, partition=parent.partition,
    )
    missing_root = replace(
        wrong_family, replay_request_id="missing-root", failure_snapshot_id="does-not-exist"
    )
    store.append(wrong_family)
    store.append(missing_root)
    report = store.validate()
    assert not report.ok
    text = "\n".join(report.broken_lineage)
    assert "wrong-family" in text and "root family" in text
    assert "missing-root" in text and "missing root failure" in text


def test_result_root_and_child_must_remain_in_request_family(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    visible = store.put_asset({"request": 1})
    output = store.put_asset({"output": 1})
    raw = store.put_asset({"raw": 1})
    root = fixture(visible)
    other_root = fixture(visible, failure_snapshot_id="fail-other", focus_observation_id="obs-other")
    parent = fixture(
        visible, failure_snapshot_id="fail-parent", focus_observation_id="obs-parent",
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        state_hash="2" * 64,
    )
    wrong_child = fixture(
        visible, failure_snapshot_id="wrong-child", focus_observation_id="obs-child",
        parent_failure_snapshot_id=other_root.failure_snapshot_id,
        parent_state_hash=other_root.state_hash, state_hash="3" * 64,
    )
    for record in (root, other_root, parent, wrong_child):
        store.append(record)
    request = ReplayRequest(
        replay_request_id="req", failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=parent.failure_snapshot_id, parent_state_hash=parent.state_hash,
        decision_id="D", hypothesis_id="H", expected_causal_implication="reproduce branch",
        mode=ReplayMode.EXACT, source_model_id=parent.source_model_id,
        source_model_digest=parent.source_model_digest, target_model_id=parent.source_model_id,
        target_model_digest=parent.source_model_digest, partition=parent.partition,
    )
    store.append(request)
    store.append(ReplayResult(
        replay_result_id="bad-result", replay_request_id=request.replay_request_id,
        failure_snapshot_id=other_root.failure_snapshot_id,
        parent_failure_snapshot_id=parent.failure_snapshot_id, parent_state_hash=parent.state_hash,
        mode=request.mode, target_model_id=request.target_model_id,
        target_model_digest=request.target_model_digest, partition=request.partition,
        completed=True, semantic_pass=False, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
        failure_classes=("SEMANTIC_FAIL",), child_failure_snapshot_id=wrong_child.failure_snapshot_id,
    ))
    report = store.validate()
    assert not report.ok
    text = "\n".join(report.broken_lineage)
    assert "bad-result" in text and "root identity mismatch" in text
    assert "bad-result" in text and "incorrect child parent/state lineage" in text


def test_failure_request_result_child_and_supersession_broken_links(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"x": 1})
    orphan = fixture(asset, failure_snapshot_id="orphan", parent_failure_snapshot_id="missing",
                     parent_state_hash="3" * 64)
    store.append(orphan)
    request = ReplayRequest(
        replay_request_id="bad-request", failure_snapshot_id="orphan",
        parent_failure_snapshot_id="orphan", parent_state_hash="3" * 64,
        decision_id="D", hypothesis_id="H", expected_causal_implication="reproduce", mode=ReplayMode.EXACT,
        source_model_id="wrong", source_model_digest="digest", target_model_id="wrong",
        target_model_digest="digest", partition=Partition.TRAINING,
    )
    store.append(request)
    store.supersede("a" * 64, "b" * 64, "links intentionally absent")
    report = store.validate()
    assert not report.ok
    text = "\n".join(report.broken_lineage)
    assert "orphan" in text and "bad-request" in text
    assert "missing old record" in text and "missing replacement record" in text
