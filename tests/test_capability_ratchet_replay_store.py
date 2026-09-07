from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

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


def rewrite_manifest(root) -> None:
    registry = root / "TEST_REPLAY.jsonl"
    (root / "TEST_REPLAY.sha256").write_text(
        hashlib.sha256(registry.read_bytes()).hexdigest() + "\n", encoding="ascii"
    )


def request_for(parent: FailureFixture, *, request_id: str = "req-1") -> ReplayRequest:
    root_id = parent.failure_snapshot_id if parent.parent_failure_snapshot_id is None else "fail-1"
    return ReplayRequest(
        replay_request_id=request_id, failure_snapshot_id=root_id,
        parent_failure_snapshot_id=parent.failure_snapshot_id, parent_state_hash=parent.state_hash,
        decision_id="D1", hypothesis_id="H1", expected_causal_implication="reproduce branch",
        mode=ReplayMode.EXACT, source_model_id=parent.source_model_id,
        source_model_digest=parent.source_model_digest, target_model_id=parent.source_model_id,
        target_model_digest=parent.source_model_digest, partition=parent.partition,
    )


def test_canonical_durable_append_assets_idempotence_and_manifest(tmp_path, monkeypatch) -> None:
    store = ReplayStore(tmp_path)
    fsynced_sizes: list[int] = []
    monkeypatch.setattr(
        "inverted.capability_ratchet.replay_store.os.fsync",
        lambda descriptor: fsynced_sizes.append(os.fstat(descriptor).st_size),
    )
    digest = store.put_asset({"unicode": "café", "a": [2, 1]})
    assert store.put_asset({"a": [2, 1], "unicode": "café"}) == digest
    assert store.read_asset(digest) == {"a": [2, 1], "unicode": "café"}
    fsynced_sizes.clear()
    record_id = store.append(fixture(digest))
    assert store.append(fixture(digest)) == record_id
    rows = (tmp_path / "TEST_REPLAY.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert rows[0] == json.dumps(json.loads(rows[0]), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert json.loads(rows[0])["record_id"] == record_id
    assert (tmp_path / "TEST_REPLAY.jsonl").stat().st_size in fsynced_sizes
    manifest = (tmp_path / "TEST_REPLAY.sha256").read_text(encoding="ascii").strip()
    assert manifest == hashlib.sha256((tmp_path / "TEST_REPLAY.jsonl").read_bytes()).hexdigest()
    assert store.validate().ok


def test_append_only_supersession_and_registry_tamper(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    old = store.append(fixture(asset))
    new = store.append(fixture(asset, focus_observation_id="obs-corrected"))
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
    request = request_for(root)
    store.append(request)
    child = fixture(visible, failure_snapshot_id="fail-child", focus_observation_id="obs-child",
                    parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
                    state_hash="3" * 64)
    store.append(child)
    result = ReplayResult(
        replay_result_id="result-1", replay_request_id="req-1",
        failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=root.failure_snapshot_id,
        parent_state_hash=root.state_hash, mode=ReplayMode.EXACT, target_model_id="model",
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


def test_identical_retry_repairs_manifest_after_post_append_crash(tmp_path, monkeypatch) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    original_write_manifest = store._write_manifest
    monkeypatch.setattr(store, "_write_manifest", lambda: (_ for _ in ()).throw(OSError("crash")))

    with pytest.raises(OSError, match="crash"):
        store.append(fixture(asset))

    assert len((tmp_path / "TEST_REPLAY.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert not store.validate().ok
    monkeypatch.setattr(store, "_write_manifest", original_write_manifest)
    record_id = store.append(fixture(asset))

    assert len(store.records()) == 1
    assert store.records()[0].record_id == record_id
    assert store.validate().ok


def test_identical_retry_repairs_only_a_final_row_after_a_committed_prefix(tmp_path, monkeypatch) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    second = fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2")
    original_write_manifest = store._write_manifest
    monkeypatch.setattr(store, "_write_manifest", lambda: (_ for _ in ()).throw(OSError("crash")))

    with pytest.raises(OSError, match="crash"):
        store.append(second)

    monkeypatch.setattr(store, "_write_manifest", original_write_manifest)
    record_id = store.append(second)

    assert len(store.records()) == 2
    assert store.records()[-1].record_id == record_id
    assert store.validate().ok


def test_identical_retry_with_current_full_manifest_does_not_rewrite_it(tmp_path, monkeypatch) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    record = fixture(asset)
    record_id = store.append(record)
    manifest_before = (tmp_path / "TEST_REPLAY.sha256").read_bytes()
    monkeypatch.setattr(store, "_write_manifest", lambda: (_ for _ in ()).throw(AssertionError("rewrite")))

    assert store.append(record) == record_id
    assert (tmp_path / "TEST_REPLAY.sha256").read_bytes() == manifest_before


def test_retry_rejects_tampered_canonical_prefix_and_preserves_manifest(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    first = fixture(asset)
    final = fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2")
    store.append(first)
    store.append(final)
    registry = tmp_path / "TEST_REPLAY.jsonl"
    rows = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines()]
    rows[0]["focus_observation_id"] = "tampered"
    unhashed = dict(rows[0])
    unhashed.pop("record_id")
    rows[0]["record_id"] = hashlib.sha256(
        json.dumps(unhashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    registry.write_bytes(
        b"".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            + b"\n"
            for row in rows
        )
    )
    manifest = tmp_path / "TEST_REPLAY.sha256"
    stale_manifest = manifest.read_bytes()

    with pytest.raises(ValueError, match="unsafe repair"):
        store.append(final)

    assert manifest.read_bytes() == stale_manifest


def test_retry_rejects_missing_manifest_when_registry_has_a_nonempty_prefix(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    first = fixture(asset)
    final = fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2")
    store.append(first)
    store.append(final)
    manifest = tmp_path / "TEST_REPLAY.sha256"
    manifest.unlink()

    with pytest.raises(ValueError, match="unsafe repair"):
        store.append(final)

    assert not manifest.exists()


def test_append_rejects_an_uncommitted_nonempty_registry_prefix(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    registry = tmp_path / "TEST_REPLAY.jsonl"
    registry_before = registry.read_bytes()
    manifest = tmp_path / "TEST_REPLAY.sha256"
    manifest.unlink()
    different = fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2")

    with pytest.raises(ValueError, match="manifest mismatch"):
        store.append(different)

    assert registry.read_bytes() == registry_before
    assert not manifest.exists()


def test_retry_cannot_repair_when_matching_record_is_not_the_final_row(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    first = fixture(asset)
    second = fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2")
    store.append(first)
    store.append(second)
    manifest = tmp_path / "TEST_REPLAY.sha256"
    manifest.write_bytes(hashlib.sha256(b"").hexdigest().encode("ascii") + b"\n")
    manifest_before = manifest.read_bytes()

    with pytest.raises(ValueError, match="unsafe repair"):
        store.append(first)

    assert manifest.read_bytes() == manifest_before


def test_superseded_correction_preserves_logical_failure_identity_and_original_bytes(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    old_id = store.append(fixture(asset))
    original_row = (tmp_path / "TEST_REPLAY.jsonl").read_bytes()
    replacement = fixture(asset, focus_observation_id="obs-corrected", oracle_ref="oracle-v2")
    replacement_id = store.append(replacement)
    store.supersede(old_id, replacement_id, "corrected fixture metadata")

    assert (tmp_path / "TEST_REPLAY.jsonl").read_bytes().splitlines(keepends=True)[0] == original_row
    assert store.get_failure("fail-1") == replace(replacement, record_id=replacement_id)
    assert store.validate().ok


def test_unlinked_duplicate_logical_failure_identity_is_invalid(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    store.append(fixture(asset, focus_observation_id="unlinked-correction"))

    report = store.validate()
    assert not report.ok
    assert any("failure identity fail-1" in item for item in report.broken_lineage)


def test_supersession_rejects_unrelated_identity_cross_type_and_cycles(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    first = store.append(fixture(asset))
    second = store.append(fixture(asset, failure_snapshot_id="fail-2", focus_observation_id="obs-2"))
    request_id = store.append(request_for(fixture(asset)))
    store.supersede(first, second, "unrelated logical fixture")
    store.supersede(second, first, "cycle")
    store.supersede(first, request_id, "cross type")

    report = store.validate()
    text = "\n".join(report.broken_lineage)
    assert not report.ok
    assert "logical identity" in text
    assert "cycle" in text
    assert "record type" in text


def test_duplicate_logical_replay_result_id_is_invalid(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    visible = store.put_asset({"request": 1})
    output = store.put_asset({"output": 1})
    raw = store.put_asset({"raw": 1})
    root = fixture(visible)
    request = request_for(root)
    for record in (root, request):
        store.append(record)
    common = dict(
        replay_result_id="result-1", replay_request_id=request.replay_request_id,
        failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        mode=request.mode, target_model_id=request.target_model_id,
        target_model_digest=request.target_model_digest, partition=request.partition,
        completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
    )
    store.append(ReplayResult(**common))
    store.append(ReplayResult(**common, metadata={"attempt": 2}))

    report = store.validate()
    assert not report.ok
    assert any("result identity result-1" in item for item in report.broken_lineage)


def test_request_and_result_corrections_are_valid_when_each_has_one_supersession_chain(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    visible = store.put_asset({"request": 1})
    output = store.put_asset({"output": 1})
    raw = store.put_asset({"raw": 1})
    root = fixture(visible)
    old_request = request_for(root)
    new_request = replace(old_request, metadata={"correction": 1})
    for record in (root, old_request, new_request):
        record_id = store.append(record)
        if record is old_request:
            old_request_id = record_id
        elif record is new_request:
            new_request_id = record_id
    store.supersede(old_request_id, new_request_id, "request correction")
    result_fields = dict(
        replay_result_id="result-1", replay_request_id=new_request.replay_request_id,
        failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        mode=new_request.mode, target_model_id=new_request.target_model_id,
        target_model_digest=new_request.target_model_digest, partition=new_request.partition,
        completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
    )
    old_result_id = store.append(ReplayResult(**result_fields))
    new_result_id = store.append(ReplayResult(**result_fields, metadata={"correction": 1}))
    store.supersede(old_result_id, new_result_id, "result correction")

    assert store.validate().ok


def test_non_root_failure_must_be_claimed_by_exactly_one_result(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    root = fixture(asset)
    orphan = fixture(
        asset, failure_snapshot_id="orphan-child", focus_observation_id="orphan",
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        state_hash="2" * 64,
    )
    store.append(root)
    store.append(orphan)

    report = store.validate()
    assert not report.ok
    assert any("orphan-child" in item and "not claimed" in item for item in report.broken_lineage)


def test_child_failure_cannot_be_claimed_by_multiple_results(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    visible = store.put_asset({"request": 1})
    output = store.put_asset({"output": 1})
    raw = store.put_asset({"raw": 1})
    root = fixture(visible)
    child = fixture(
        visible, failure_snapshot_id="child", focus_observation_id="child",
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        state_hash="2" * 64,
    )
    requests = (request_for(root, request_id="req-a"), request_for(root, request_id="req-b"))
    for record in (root, child, *requests):
        store.append(record)
    for index, request in enumerate(requests):
        store.append(ReplayResult(
            replay_result_id=f"result-{index}", replay_request_id=request.replay_request_id,
            failure_snapshot_id=root.failure_snapshot_id,
            parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
            mode=request.mode, target_model_id=request.target_model_id,
            target_model_digest=request.target_model_digest, partition=request.partition,
            completed=True, semantic_pass=False, contract_pass=True,
            output_asset_sha256=output, raw_call_asset_sha256=raw,
            failure_classes=("SEMANTIC_FAIL",), child_failure_snapshot_id=child.failure_snapshot_id,
        ))

    report = store.validate()
    assert not report.ok
    assert any("child" in item and "multiple" in item for item in report.broken_lineage)


def test_child_failure_family_must_match_parent_and_root_family(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    visible = store.put_asset({"request": 1})
    output = store.put_asset({"output": 1})
    raw = store.put_asset({"raw": 1})
    root = fixture(visible, family="ARITHMETIC")
    child = fixture(
        visible, failure_snapshot_id="family-mismatch-child", focus_observation_id="child",
        family="CODING", parent_failure_snapshot_id=root.failure_snapshot_id,
        parent_state_hash=root.state_hash, state_hash="2" * 64,
    )
    request = request_for(root)
    for record in (root, child, request):
        store.append(record)
    store.append(ReplayResult(
        replay_result_id="family-mismatch-result", replay_request_id=request.replay_request_id,
        failure_snapshot_id=root.failure_snapshot_id,
        parent_failure_snapshot_id=root.failure_snapshot_id, parent_state_hash=root.state_hash,
        mode=request.mode, target_model_id=request.target_model_id,
        target_model_digest=request.target_model_digest, partition=request.partition,
        completed=True, semantic_pass=False, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
        failure_classes=("SEMANTIC_FAIL",), child_failure_snapshot_id=child.failure_snapshot_id,
    ))

    report = store.validate()

    assert not report.ok
    assert any("family-mismatch-child" in item and "family mismatch" in item for item in report.broken_lineage)


@pytest.mark.parametrize(
    "rewrite",
    (
        lambda canonical: canonical + b"\n",
        lambda canonical: b" " + canonical,
        lambda canonical: canonical.rstrip(b"\n") + b" \n",
        lambda canonical: canonical.rstrip(b"\n"),
        lambda canonical: json.dumps(
            dict(reversed(list(json.loads(canonical).items()))), ensure_ascii=False
        ).encode("utf-8") + b"\n",
    ),
    ids=("blank-row", "leading-space", "trailing-space", "missing-newline", "alternate-order-pretty"),
)
def test_registry_rejects_noncanonical_physical_jsonl_even_with_matching_manifest(tmp_path, rewrite) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    registry = tmp_path / "TEST_REPLAY.jsonl"
    registry.write_bytes(rewrite(registry.read_bytes()))
    rewrite_manifest(tmp_path)

    report = store.validate()
    assert not report.ok
    assert any("canonical" in item or "blank" in item or "newline" in item for item in report.broken_lineage)


@pytest.mark.parametrize("raw", (b'{"z": 1}', b"not-json"), ids=("noncanonical", "unusable"))
def test_assets_must_be_canonical_usable_json_even_when_hash_matches(tmp_path, raw) -> None:
    digest = hashlib.sha256(raw).hexdigest()
    asset_root = tmp_path / "replay-assets" / "sha256"
    asset_root.mkdir(parents=True)
    (asset_root / f"{digest}.json").write_bytes(raw)
    store = ReplayStore(tmp_path)
    store.append(fixture(digest))

    with pytest.raises(ValueError, match="canonical JSON"):
        store.read_asset(digest)
    report = store.validate()
    assert not report.ok
    assert digest in report.hash_mismatches


@pytest.mark.parametrize("digest", ("a" * 63, "A" * 64, "../" + "a" * 61))
def test_read_asset_rejects_invalid_digest_syntax(tmp_path, digest) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        ReplayStore(tmp_path).read_asset(digest)


@pytest.mark.parametrize(
    "manifest_bytes",
    (
        lambda digest: digest.encode("ascii"),
        lambda digest: digest.encode("ascii") + b"\n\n",
        lambda digest: b" " + digest.encode("ascii") + b"\n",
        lambda digest: digest.upper().encode("ascii") + b"\n",
        lambda digest: digest.encode("ascii") + "\N{SNOWMAN}".encode("utf-8") + b"\n",
    ),
    ids=("missing-newline", "extra-newline", "leading-space", "uppercase", "non-ascii"),
)
def test_manifest_physical_bytes_must_be_canonical_and_validate_never_crashes(
    tmp_path, manifest_bytes
) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    registry_digest = hashlib.sha256((tmp_path / "TEST_REPLAY.jsonl").read_bytes()).hexdigest()
    (tmp_path / "TEST_REPLAY.sha256").write_bytes(manifest_bytes(registry_digest))

    report = store.validate()

    assert not report.ok
    assert "TEST_REPLAY.sha256" in report.hash_mismatches


def test_manifest_io_problem_returns_invalid_report_instead_of_raising(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    manifest = tmp_path / "TEST_REPLAY.sha256"
    manifest.unlink()
    manifest.mkdir()

    report = store.validate()

    assert not report.ok
    assert "TEST_REPLAY.sha256" in report.hash_mismatches


def test_registry_io_problem_returns_invalid_report_instead_of_raising(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    registry = tmp_path / "TEST_REPLAY.jsonl"
    registry.unlink()
    registry.mkdir()

    report = store.validate()

    assert not report.ok
    assert any("registry read error" in item for item in report.broken_lineage)


def test_registry_io_problem_during_row_read_returns_invalid_report(tmp_path, monkeypatch) -> None:
    store = ReplayStore(tmp_path)
    asset = store.put_asset({"request": 1})
    store.append(fixture(asset))
    registry_reads = 0
    original_read_bytes = type(store.registry_path).read_bytes

    def fail_second_registry_read(path):
        nonlocal registry_reads
        if path == store.registry_path:
            registry_reads += 1
            if registry_reads == 2:
                raise PermissionError("registry became unreadable")
        return original_read_bytes(path)

    monkeypatch.setattr(type(store.registry_path), "read_bytes", fail_second_registry_read)

    report = store.validate()

    assert not report.ok
    assert any("registry read error" in item for item in report.broken_lineage)


def test_referenced_asset_io_problem_returns_invalid_report_and_digest(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    digest = store.put_asset({"request": 1})
    store.append(fixture(digest))
    asset = tmp_path / "replay-assets" / "sha256" / f"{digest}.json"
    asset.unlink()
    asset.mkdir()

    report = store.validate()

    assert not report.ok
    assert digest in report.hash_mismatches


def test_two_store_instances_racing_identical_append_write_one_row(tmp_path, monkeypatch) -> None:
    asset = ReplayStore(tmp_path).put_asset({"request": 1})
    stores = (ReplayStore(tmp_path), ReplayStore(tmp_path))
    start = threading.Barrier(2)
    read_race = threading.Barrier(2)
    original_raw_rows = ReplayStore._raw_rows
    first_reads: set[int] = set()
    guard = threading.Lock()

    def synchronized_first_read(store):
        rows = original_raw_rows(store)
        should_wait = False
        if threading.current_thread() is not threading.main_thread():
            with guard:
                if id(store) not in first_reads:
                    first_reads.add(id(store))
                    should_wait = True
        if should_wait:
            try:
                read_race.wait(timeout=0.25)
            except threading.BrokenBarrierError:
                pass
        return rows

    monkeypatch.setattr(ReplayStore, "_raw_rows", synchronized_first_read)

    def append(store):
        start.wait()
        return store.append(fixture(asset))

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = tuple(executor.map(append, stores))

    assert ids[0] == ids[1]
    assert len((tmp_path / "TEST_REPLAY.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert ReplayStore(tmp_path).validate().ok


def test_separate_processes_racing_identical_append_write_one_row(tmp_path) -> None:
    asset = ReplayStore(tmp_path).put_asset({"request": 1})
    worker = """
import sys
import time
from pathlib import Path
sys.path.insert(0, sys.argv[4])
from inverted.capability_ratchet import FailureFixture, Partition
from inverted.capability_ratchet.replay_store import ReplayStore

root, asset, worker_id = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
(root / ("ready-" + worker_id)).write_text("ready", encoding="ascii")
deadline = time.monotonic() + 10
while not (root / "start").exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("start gate")
    time.sleep(0.01)
record = FailureFixture(
    failure_snapshot_id="fail-1", source_campaign_id="campaign", source_trial_id="trial",
    focus_observation_id="obs", focus_task_id="task", batch_task_ids=("task",),
    family="ARITHMETIC", failure_classes=("SEMANTIC_FAIL",), source_model_id="model",
    source_model_digest="digest", source_runtime={"provider": "fake"},
    inference_profile={"temperature": 0}, inference_seed=1, partition=Partition.DEVELOPMENT,
    model_visible_asset_sha256=asset, state_hash="1" * 64, oracle_ref="oracle",
    expected_contract="answer", source_evidence_refs=("raw:1",),
)
print(ReplayStore(root).append(record), flush=True)
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable, "-c", worker, str(tmp_path), asset, str(index),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for index in range(2)
    ]
    deadline = time.monotonic() + 10
    while not all((tmp_path / f"ready-{index}").exists() for index in range(2)):
        if time.monotonic() >= deadline:
            for process in processes:
                process.kill()
            pytest.fail("worker processes did not reach the start gate")
        time.sleep(0.01)
    (tmp_path / "start").write_text("start", encoding="ascii")
    completed = [process.communicate(timeout=10) for process in processes]

    assert all(process.returncode == 0 for process in processes), completed
    assert completed[0][0].strip() == completed[1][0].strip()
    assert len((tmp_path / "TEST_REPLAY.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    manifest = (tmp_path / "TEST_REPLAY.sha256").read_bytes()
    registry_digest = hashlib.sha256((tmp_path / "TEST_REPLAY.jsonl").read_bytes()).hexdigest()
    assert manifest == registry_digest.encode("ascii") + b"\n"
    assert ReplayStore(tmp_path).validate().ok
