from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from inverted.capability_ratchet import (
    FailureFixture,
    Partition,
    ReplayCompletion,
    ReplayExecutor,
    ReplayMode,
    ReplayRequest,
    ReplaySelector,
    ReplayStore,
    V2EvidenceSource,
    seed_v2_failures,
    select_failures,
)


def _canonical(payload) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _task(index: int) -> dict:
    return {
        "task_id": f"pre-{index}",
        "family": "ARITHMETIC",
        "difficulty": 2,
        "prompt": f"Compute {index}+10",
        "expected": index + 10,
        "scorer": "exact_value",
        "contract": "answer_object",
        "metadata": [],
    }


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mini_v2(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tasks = [_task(index) for index in range(5)]
    pool = {"protocol_version": 2, "seed": 99, "tasks": tasks}
    _write_json(root / "task-pool-v2.json", pool)
    manifest = {
        "protocol_version": 2,
        "task_pool_sha256": hashlib.sha256(_canonical(pool)).hexdigest(),
        "runtime_provenance": {
            "provider": "fake",
            "model": "qwen3.5:9b-q8_0",
            "model_digest": "digest-v2",
            "version": "1",
        },
    }
    _write_json(root / "protocol-v2-manifest.json", manifest)
    batch_text = "\n\n".join(f"TASK {task['task_id']}\n{task['prompt']}" for task in tasks)
    request = {
        "model": "qwen3.5:9b-q8_0",
        "stream": False,
        "think": False,
        "options": {"seed": 17, "temperature": 0.7, "num_predict": 768},
        "messages": [{"role": "user", "content": batch_text}],
    }
    raw = {
        "trial_id": "trial-preflight",
        "physical_calls": 1,
        "raw_calls": [{
            "request": request,
            "response": {"model": "qwen3.5:9b-q8_0", "done": True,
                         "done_reason": "stop", "eval_count": 10,
                         "message": {"content": '{"answers":[]}'}}
        }],
        "responses": [
            '{"answer":10}',
            '{"answer":999}',
            '{"result":12}',
            "",
            '{"answer":14}',
        ],
    }
    (root / "raw_calls.jsonl").write_text(json.dumps(raw) + "\n", encoding="utf-8")

    states = [
        (True, True, True, (), '{"answer":10}'),
        (False, True, True, ("SEMANTIC_FAIL",), '{"answer":999}'),
        (True, False, True, ("CONTRACT_FAIL",), '{"result":12}'),
        (False, False, False, ("COMPLETION_FAIL",), ""),
        (True, True, True, (), '{"answer":14}'),
    ]
    rows = []
    for index, task in enumerate(tasks):
        semantic, contract, completed, failures, response = states[index]
        rows.append({
            "observation_id": f"obs-{index}",
            "batch_id": "ARITHMETIC:gate:000",
            "task_id": task["task_id"],
            "family": "ARITHMETIC",
            "stage": "gate",
            "profile": {"thinking_budget": 0, "temperature": 0.7,
                        "top_p": None, "top_k": None, "min_p": None,
                        "presence_penalty": None, "repeat_penalty": None},
            "inference_seed": 17,
            "decision_reason": "PREFLIGHT",
            "semantic_pass": semantic,
            "contract_pass": contract,
            "completed": completed,
            "semantic_quality": 1.0 if semantic else 0.0,
            "contract_quality": 1.0 if contract else 0.0,
            "latency_s": 0.1,
            "output_tokens": 4 if completed else 0,
            "thinking_tokens": 0,
            "physical_calls": 1 if index == 0 else 0,
            "response_text": response,
            "failure_classes": list(failures),
            "raw_call_refs": ["trial-preflight:call:0"],
            "metadata": [["trial_id", "trial-preflight"]],
        })
    (root / "atomic_observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return root


class FakeReplayAdapter:
    def __init__(self, *, model="qwen3.5:9b-q8_0", digest="digest-v2",
                 semantic=True, contract=True, completed=True) -> None:
        self.model = model
        self.digest = digest
        self.semantic = semantic
        self.contract = contract
        self.completed = completed
        self.calls = []

    def runtime_provenance(self):
        return {"provider": "fake", "model": self.model,
                "model_digest": self.digest, "version": "1"}

    def execute_fixture(self, fixture, visible_payload, request):
        self.calls.append((fixture, visible_payload, request))
        raw_calls = []
        for frozen in visible_payload["request_envelopes"]:
            actual = json.loads(json.dumps(frozen))
            if request.mode is ReplayMode.CROSS_MODEL:
                actual["model"] = request.target_model_id
            raw_calls.append({
                "request": actual,
                "response": {"model": request.target_model_id, "done": self.completed,
                             "message": {"content": '{"answer":10}'}}
            })
        failures = []
        if not self.completed:
            failures.append("COMPLETION_FAIL")
        if not self.semantic:
            failures.append("SEMANTIC_FAIL")
        if not self.contract:
            failures.append("CONTRACT_FAIL")
        return ReplayCompletion(
            completed=self.completed,
            semantic_pass=self.semantic,
            contract_pass=self.contract,
            output_payload={"answer": 10 if self.semantic else "wrong"},
            raw_calls=tuple(raw_calls),
            failure_classes=tuple(failures),
            metrics={"physical_calls": len(raw_calls), "latency_s": 0.01},
        )


def _exact(fixture: FailureFixture, request_id: str) -> ReplayRequest:
    return ReplayRequest.for_exact(
        fixture,
        decision_id=f"D-{request_id}",
        hypothesis_id=f"H-{request_id}",
        request_id=request_id,
    )


def test_replay_kernel_end_to_end_zero_inference(tmp_path, monkeypatch) -> None:
    from inverted.universal_tuning import qwen_ollama

    def forbidden_model_path(*args, **kwargs):
        raise AssertionError("preflight attempted a real Qwen/Ollama path")

    monkeypatch.setattr(qwen_ollama.QwenOllamaAdapter, "runtime_provenance", forbidden_model_path)
    monkeypatch.setattr(qwen_ollama.QwenOllamaAdapter, "post_chat_payload", forbidden_model_path)

    source = V2EvidenceSource(_mini_v2(tmp_path / "source"))
    store = ReplayStore(tmp_path / "replay")
    seeded = seed_v2_failures(source, store)
    assert seeded.total_observations == 5
    assert seeded.material_failures == 3
    assert seeded.fixtures_added == 3
    assert seeded.invalid_rows == 0

    fixtures = select_failures(
        store, ReplaySelector(source_model="qwen3.5:9b-q8_0")
    )
    assert len(fixtures) == 3
    root = next(item for item in fixtures if item.focus_task_id == "pre-1")
    root_before = store.get_failure(root.failure_snapshot_id)
    registry_before = store.registry_path.read_bytes()

    success_adapter = FakeReplayAdapter()
    success = ReplayExecutor(
        store, {root.source_model_id: success_adapter}
    ).execute(_exact(root, "replay-success"))
    assert success.completed and success.semantic_pass and success.contract_pass
    assert success.child_failure_snapshot_id is None
    assert store.registry_path.read_bytes().startswith(registry_before)
    assert store.get_failure(root.failure_snapshot_id) == root_before
    assert store.validate().ok

    fail_adapter = FakeReplayAdapter(semantic=False)
    failed = ReplayExecutor(
        store, {root.source_model_id: fail_adapter}
    ).execute(_exact(root, "replay-fail"))
    assert failed.child_failure_snapshot_id is not None
    child = store.get_failure(failed.child_failure_snapshot_id)
    assert child.parent_failure_snapshot_id == root.failure_snapshot_id
    assert child.parent_state_hash == root.state_hash
    assert child.partition is root.partition
    assert child.oracle_asset_sha256 == root.oracle_asset_sha256
    assert child.forensic_asset_sha256 == failed.raw_call_asset_sha256
    assert store.validate().ok


@pytest.fixture(autouse=True)
def _forbid_real_qwen_transport(monkeypatch):
    from inverted.universal_tuning import qwen_ollama

    def forbidden(*args, **kwargs):
        raise AssertionError("preflight attempted a real Qwen/Ollama path")

    monkeypatch.setattr(qwen_ollama.QwenOllamaAdapter, "runtime_provenance", forbidden)
    monkeypatch.setattr(qwen_ollama.QwenOllamaAdapter, "post_chat_payload", forbidden)


def _seeded_root(tmp_path: Path, name: str):
    source = V2EvidenceSource(_mini_v2(tmp_path / f"source-{name}"))
    store = ReplayStore(tmp_path / f"replay-{name}")
    seeded = seed_v2_failures(source, store)
    assert seeded.material_failures == 3
    root = next(
        fixture for fixture in select_failures(
            store, ReplaySelector(source_model="qwen3.5:9b-q8_0")
        )
        if fixture.focus_task_id == "pre-1"
    )
    return store, root


def _cross(
    fixture: FailureFixture,
    request_id: str,
    *,
    target_model: str = "qwen-other:9b",
    target_digest: str = "digest-other",
) -> ReplayRequest:
    return ReplayRequest(
        replay_request_id=request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        decision_id=f"D-{request_id}",
        hypothesis_id=f"H-{request_id}",
        expected_causal_implication="measure transfer to a compatible target model",
        mode=ReplayMode.CROSS_MODEL,
        source_model_id=fixture.source_model_id,
        source_model_digest=fixture.source_model_digest,
        target_model_id=target_model,
        target_model_digest=target_digest,
        partition=fixture.partition,
        changed_dimensions=("target_model",),
        overrides={},
    )


def test_cross_model_replay_targets_same_source_without_source_mutation(tmp_path) -> None:
    store, root = _seeded_root(tmp_path, "cross")
    source_before = store.get_failure(root.failure_snapshot_id)
    visible_before = store.read_asset(root.model_visible_asset_sha256)

    exact = ReplayExecutor(
        store, {root.source_model_id: FakeReplayAdapter()}
    ).execute(_exact(root, "exact-distinct"))

    target = FakeReplayAdapter(model="qwen-other:9b", digest="digest-other")
    cross = ReplayExecutor(store, {target.model: target}).execute(
        _cross(root, "cross-distinct")
    )

    assert exact.mode is ReplayMode.EXACT
    assert cross.mode is ReplayMode.CROSS_MODEL
    assert cross.target_model_id == "qwen-other:9b"
    raw = store.read_asset(cross.raw_call_asset_sha256)
    assert all(call["request"]["model"] == "qwen-other:9b" for call in raw["raw_calls"])
    assert store.get_failure(root.failure_snapshot_id) == source_before
    assert store.read_asset(root.model_visible_asset_sha256) == visible_before
    result_modes = {
        record.mode
        for record in store.records()
        if getattr(record, "replay_result_id", None) is not None
    }
    assert {ReplayMode.EXACT, ReplayMode.CROSS_MODEL}.issubset(result_modes)
    assert store.validate().ok


def test_fresh_to_sealed_partition_contamination_is_rejected_before_adapter(tmp_path) -> None:
    store, root = _seeded_root(tmp_path, "partition")
    fresh = replace(
        root,
        failure_snapshot_id="fresh-preflight-root",
        focus_observation_id="fresh-obs",
        partition=Partition.FRESH,
        record_id=None,
    )
    store.append(fresh)
    fresh = store.get_failure(fresh.failure_snapshot_id)
    adapter = FakeReplayAdapter()
    contaminated = replace(
        _exact(fresh, "fresh-to-sealed"),
        partition=Partition.SEALED,
    )

    with pytest.raises(ValueError, match="partition"):
        ReplayExecutor(store, {fresh.source_model_id: adapter}).execute(contaminated)

    assert adapter.calls == []
    assert store.get_failure(fresh.failure_snapshot_id).partition is Partition.FRESH
    assert store.validate().ok


def test_asset_tamper_blocks_execution_before_adapter_call(tmp_path) -> None:
    store, root = _seeded_root(tmp_path, "tamper")
    adapter = FakeReplayAdapter()
    asset = store.asset_root / f"{root.model_visible_asset_sha256}.json"
    asset.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="integrity|asset"):
        ReplayExecutor(store, {root.source_model_id: adapter}).execute(
            _exact(root, "tamper-block")
        )

    assert adapter.calls == []
    report = store.validate()
    assert not report.ok
    assert root.model_visible_asset_sha256 in report.hash_mismatches


def test_supersession_preserves_original_row_and_selects_replacement(tmp_path) -> None:
    store, root = _seeded_root(tmp_path, "supersede")
    assert root.record_id is not None
    original_line = next(
        line
        for line in store.registry_path.read_bytes().splitlines(keepends=True)
        if root.record_id.encode("ascii") in line
    )

    replacement = replace(
        root,
        focus_observation_id="obs-corrected-preflight",
        metadata={**dict(root.metadata), "correction": "preflight"},
        record_id=None,
    )
    replacement_id = store.append(replacement)
    store.supersede(root.record_id, replacement_id, "preflight correction")

    rows = store.registry_path.read_bytes().splitlines(keepends=True)
    assert original_line in rows
    active = store.get_failure(root.failure_snapshot_id)
    assert active.record_id == replacement_id
    assert active.focus_observation_id == "obs-corrected-preflight"
    assert any(getattr(record, "record_id", None) == root.record_id for record in store.records())
    assert store.validate().ok


def test_registry_reconstructs_from_jsonl_and_verified_assets_only(tmp_path) -> None:
    store, root = _seeded_root(tmp_path, "reconstruct")
    ReplayExecutor(
        store, {root.source_model_id: FakeReplayAdapter()}
    ).execute(_exact(root, "reconstruct-exact"))
    assert store.validate().ok

    reconstructed_root = tmp_path / "reconstructed"
    reconstructed_root.mkdir()
    shutil.copy2(store.registry_path, reconstructed_root / "TEST_REPLAY.jsonl")
    shutil.copy2(store.manifest_path, reconstructed_root / "TEST_REPLAY.sha256")
    shutil.copytree(store.root / "replay-assets", reconstructed_root / "replay-assets")

    reconstructed = ReplayStore(reconstructed_root)
    assert reconstructed.validate().ok
    assert reconstructed.records() == store.records()
    reconstructed_root_fixture = reconstructed.get_failure(root.failure_snapshot_id)
    assert reconstructed_root_fixture == store.get_failure(root.failure_snapshot_id)
    assert reconstructed.read_asset(
        reconstructed_root_fixture.model_visible_asset_sha256
    ) == store.read_asset(root.model_visible_asset_sha256)
