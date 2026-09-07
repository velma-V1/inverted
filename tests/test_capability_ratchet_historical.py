from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from inverted.capability_ratchet import Partition, ReplayRecordType
from inverted.capability_ratchet.historical import V2EvidenceSource, seed_v2_failures
from inverted.capability_ratchet.replay_store import ReplayStore


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_task(index: int) -> dict:
    return {
        "task_id": f"mini-{index}", "family": "ARITHMETIC", "difficulty": 2,
        "prompt": f"Compute {index}+1", "expected": index + 1,
        "scorer": "exact_value", "contract": "answer_object", "metadata": [],
    }


def write_mini_v2(root: Path, *, failed=(1, 3), cap=False, omit_raw=False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tasks = [make_task(i) for i in range(5)]
    pool = {"protocol_version": 2, "seed": 17, "tasks": tasks}
    pool_bytes = (json.dumps(pool, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (root / "task-pool-v2.json").write_bytes(pool_bytes)
    canonical_pool = json.dumps(pool, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    manifest = {
        "protocol_version": 2,
        "task_pool_sha256": hashlib.sha256(canonical_pool).hexdigest(),
        "runtime_provenance": {
            "provider": "ollama", "ollama_version": "0.32.15",
            "model": "qwen3.5:9b-q8_0", "model_digest": "digest-v2",
            "base_url": "http://127.0.0.1:11434",
        },
    }
    write_json(root / "protocol-v2-manifest.json", manifest)
    batch_text = "\n\n".join(f"TASK {task['task_id']}\n{task['prompt']}" for task in tasks)
    first_request = {
        "model": "qwen3.5:9b-q8_0", "stream": False, "think": bool(cap),
        "options": {"seed": 91, "temperature": 1.0 if cap else 0.7,
                    "num_predict": 1024 if cap else 768},
        "messages": [{"role": "user", "content": batch_text}],
    }
    raw_calls = [{
        "request": first_request,
        "response": {"model": "qwen3.5:9b-q8_0", "done": True,
                     "done_reason": "length" if cap else "stop", "eval_count": 10,
                     "message": {"thinking": "trace" if cap else "", "content": ""}},
    }]
    trial = {"trial_id": "trial-1", "physical_calls": len(raw_calls),
             "raw_calls": raw_calls, "responses": ["{}"] * 5}
    if not omit_raw:
        (root / "raw_calls.jsonl").write_text(json.dumps(trial) + "\n", encoding="utf-8")
    else:
        (root / "raw_calls.jsonl").write_text("", encoding="utf-8")

    rows = []
    for index, task in enumerate(tasks):
        failed_here = index in failed
        rows.append({
            "observation_id": f"obs-{index}", "batch_id": "ARITHMETIC:gate:000",
            "task_id": task["task_id"], "family": "ARITHMETIC", "stage": "gate",
            "profile": {"thinking_budget": 1024 if cap else 0,
                        "temperature": 1.0 if cap else 0.7, "top_p": None,
                        "top_k": None, "min_p": None, "presence_penalty": None,
                        "repeat_penalty": None},
            "inference_seed": 91, "decision_reason": "TEST",
            "semantic_pass": not failed_here, "contract_pass": True, "completed": True,
            "semantic_quality": 0.0 if failed_here else 1.0, "contract_quality": 1.0,
            "latency_s": 0.1, "output_tokens": 4, "thinking_tokens": 10 if cap else 0,
            "physical_calls": len(raw_calls), "response_text": "wrong" if failed_here else "ok",
            "failure_classes": ["SEMANTIC_FAIL"] if failed_here else [],
            "raw_call_refs": ["trial-1:call:0"],
            "metadata": [["trial_id", "trial-1"]],
        })
    (root / "atomic_observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return root


def failure_records(store: ReplayStore):
    return tuple(
        record for record in store.records()
        if getattr(record, "record_type", None) is ReplayRecordType.FAILURE_FIXTURE
    )


def test_seed_imports_one_fixture_per_atomic_failure_and_reuses_batch_asset(tmp_path) -> None:
    source = V2EvidenceSource(write_mini_v2(tmp_path / "source"))
    store = ReplayStore(tmp_path / "replay")
    result = seed_v2_failures(source, store)
    failures = failure_records(store)

    assert result.total_observations == 5
    assert result.material_failures == 2
    assert result.fixtures_added == 2
    assert result.skipped_nonfailures == 3
    assert len(failures) == 2
    assert failures[0].model_visible_asset_sha256 == failures[1].model_visible_asset_sha256
    assert {f.focus_task_id for f in failures} == {"mini-1", "mini-3"}


def test_reasoning_cap_exhaustion_is_material_even_when_answers_pass(tmp_path) -> None:
    source = V2EvidenceSource(write_mini_v2(tmp_path / "source", failed=(), cap=True))
    store = ReplayStore(tmp_path / "replay")
    result = seed_v2_failures(source, store)
    failures = failure_records(store)

    assert result.material_failures == 5
    assert len(failures) == 5
    assert all("REASONING_CAP_EXHAUSTION" in f.failure_classes for f in failures)


def test_manifest_task_pool_hash_mismatch_aborts_before_append(tmp_path) -> None:
    root = write_mini_v2(tmp_path / "source")
    pool_path = root / "task-pool-v2.json"
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    pool["tasks"][0]["prompt"] = "tampered task prompt"
    write_json(pool_path, pool)
    store = ReplayStore(tmp_path / "replay")
    with pytest.raises(ValueError, match="hash|manifest"):
        seed_v2_failures(V2EvidenceSource(root), store)
    assert store.records() == ()


def test_missing_raw_trial_does_not_partially_append_trial(tmp_path) -> None:
    source = V2EvidenceSource(write_mini_v2(tmp_path / "source", omit_raw=True))
    store = ReplayStore(tmp_path / "replay")
    result = seed_v2_failures(source, store)
    assert result.invalid_rows == 5
    assert result.fixtures_added == 0
    assert store.records() == ()


def test_rerun_is_idempotent_and_counts_duplicates(tmp_path) -> None:
    source = V2EvidenceSource(write_mini_v2(tmp_path / "source"))
    store = ReplayStore(tmp_path / "replay")
    first = seed_v2_failures(source, store)
    rows_before = store.registry_path.read_bytes()
    second = seed_v2_failures(source, store)

    assert first.fixtures_added == 2
    assert second.fixtures_added == 0
    assert second.duplicate_fixtures == 2
    assert store.registry_path.read_bytes() == rows_before


def test_imported_partition_is_always_historical(tmp_path) -> None:
    source = V2EvidenceSource(write_mini_v2(tmp_path / "source"))
    store = ReplayStore(tmp_path / "replay")
    seed_v2_failures(source, store)
    assert all(f.partition is Partition.HISTORICAL for f in failure_records(store))


def test_duplicate_raw_trial_identity_is_rejected_before_append(tmp_path) -> None:
    root = write_mini_v2(tmp_path / "source")
    raw = (root / "raw_calls.jsonl").read_text(encoding="utf-8")
    (root / "raw_calls.jsonl").write_text(raw + raw, encoding="utf-8")
    store = ReplayStore(tmp_path / "replay")
    with pytest.raises(ValueError, match="duplicate.*trial|trial.*duplicate"):
        seed_v2_failures(V2EvidenceSource(root), store)
    assert store.records() == ()


def test_production_wrapped_manifest_is_verified_and_accepted(tmp_path) -> None:
    root = write_mini_v2(tmp_path / "source")
    manifest_path = root / "protocol-v2-manifest.json"
    inner = json.loads(manifest_path.read_text(encoding="utf-8"))
    canonical = json.dumps(inner, sort_keys=True, separators=(",", ":")).encode("utf-8")
    write_json(manifest_path, {
        "manifest": inner,
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
    })
    result = seed_v2_failures(V2EvidenceSource(root), ReplayStore(tmp_path / "replay"))
    assert result.fixtures_added == 2


def test_tampered_wrapped_manifest_aborts_before_append(tmp_path) -> None:
    root = write_mini_v2(tmp_path / "source")
    manifest_path = root / "protocol-v2-manifest.json"
    inner = json.loads(manifest_path.read_text(encoding="utf-8"))
    write_json(manifest_path, {"manifest": inner, "manifest_sha256": "0" * 64})
    store = ReplayStore(tmp_path / "replay")
    with pytest.raises(ValueError, match="manifest.*hash|hash.*manifest"):
        seed_v2_failures(V2EvidenceSource(root), store)
    assert store.records() == ()


def test_task_pool_hash_uses_v2_canonical_json_rule(tmp_path) -> None:
    root = write_mini_v2(tmp_path / "source")
    pool_path = root / "task-pool-v2.json"
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    canonical = json.dumps(pool, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    manifest_path = root / "protocol-v2-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["task_pool_sha256"] = hashlib.sha256(canonical).hexdigest()
    write_json(manifest_path, manifest)
    result = seed_v2_failures(V2EvidenceSource(root), ReplayStore(tmp_path / "replay"))
    assert result.fixtures_added == 2


def test_idempotent_reseed_does_not_rescan_registry_per_fixture(tmp_path, monkeypatch) -> None:
    source = V2EvidenceSource(write_mini_v2(tmp_path / "source"))
    store = ReplayStore(tmp_path / "replay")
    seed_v2_failures(source, store)

    def forbidden_get_failure(*args, **kwargs):
        raise AssertionError("idempotent seed must use one registry index, not per-fixture rescans")

    monkeypatch.setattr(store, "get_failure", forbidden_get_failure)
    result = seed_v2_failures(source, store)
    assert result.fixtures_added == 0
    assert result.duplicate_fixtures == 2


def test_preview_reports_seed_geometry_without_writing_replay_store(tmp_path) -> None:
    from inverted.capability_ratchet.historical import preview_v2_failures

    source = V2EvidenceSource(write_mini_v2(tmp_path / "source", failed=(1, 3), cap=False))
    preview = preview_v2_failures(source)
    assert preview.total_observations == 5
    assert preview.material_failures == 2
    assert preview.skipped_nonfailures == 3
    assert preview.invalid_rows == 0
    assert preview.fixtures_added == 0
    assert preview.duplicate_fixtures == 0
    assert not (tmp_path / "replay").exists()
