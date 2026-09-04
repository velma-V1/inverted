from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from inverted.harvest_d.d4_evidence import resolve_frozen_d4_evidence, validate_d4_evidence_root


MODEL = "qwen3.5:9b-q8_0"
DIGEST = "sha256:unit-test-qwen-digest"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_valid_d4(root: Path, *, policy_id: str = "THINK_OFF", digest: str = DIGEST) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    chat_options = {"think": False} if policy_id == "THINK_OFF" else {}
    _write_json(root / "d4_frozen_policy.json", {
        "state": "FROZEN",
        "policy_id": policy_id,
        "model_id": MODEL,
        "model_digest": digest,
        "chat_options": chat_options,
        "matched_cases": 24,
        "semantic_decision": "NO_DECISIVE_DIFFERENCE",
        "evidence_status": "PROVISIONAL_FIXED_HORIZON",
    })
    _write_json(root / "00-HARVEST-D-D4-QWEN-POLICY-MASTER-INDEX.json", {
        "protocol": "D4-QWEN-POLICY-v1",
        "mode": "REAL_LOCAL",
        "physical_model_calls": 48,
        "planned_physical_calls": 48,
        "max_calls": 48,
        "final_state": "COMPLETE",
        "policy_state": "FROZEN",
        "blind_retries_allowed": False,
    })
    _write_json(root / "d4_runtime_identity.json", {
        "protocol": "D4-QWEN-POLICY-v1",
        "model_id": MODEL,
        "model_digest": digest,
    })
    (root / "d4_call_ledger.jsonl").write_text(
        "".join(json.dumps({"experiment_id": f"D4:e{i:02d}", "committed": True, "attempt": 1}) + "\n" for i in range(48)),
        encoding="utf-8",
    )
    (root / "d4_normalized_model_calls.jsonl").write_text(
        "".join(json.dumps({"experiment_id": f"D4:e{i:02d}"}) + "\n" for i in range(48)),
        encoding="utf-8",
    )
    manifest = root / "SHA256SUMS.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "file"])
        for path in sorted(p for p in root.iterdir() if p.is_file() and p.name != manifest.name):
            writer.writerow([hashlib.sha256(path.read_bytes()).hexdigest(), path.name])
    return root


def test_validate_d4_evidence_requires_completed_48_call_real_campaign(tmp_path: Path):
    root = _write_valid_d4(tmp_path / "d4")
    evidence = validate_d4_evidence_root(root, expected_model=MODEL)
    assert evidence.policy_file == root / "d4_frozen_policy.json"
    assert evidence.model_digest == DIGEST
    assert evidence.policy_id == "THINK_OFF"
    assert evidence.physical_model_calls == 48


def test_validate_d4_evidence_rejects_model_free_or_partial_package(tmp_path: Path):
    root = _write_valid_d4(tmp_path / "d4")
    master_path = root / "00-HARVEST-D-D4-QWEN-POLICY-MASTER-INDEX.json"
    master = json.loads(master_path.read_text(encoding="utf-8"))
    master["mode"] = "MODEL_FREE"
    master["physical_model_calls"] = 0
    _write_json(master_path, master)
    with pytest.raises(ValueError, match="REAL_LOCAL.*48"):
        validate_d4_evidence_root(root, expected_model=MODEL)


def test_resolver_finds_valid_original_d4_when_default_directory_is_missing(tmp_path: Path):
    actual = _write_valid_d4(tmp_path / "old-runs" / "d4-completed")
    result = resolve_frozen_d4_evidence(
        preferred_root=tmp_path / "runs" / "harvest-d-d4-qwen-policy",
        search_roots=(tmp_path,),
        recovery_root=tmp_path / "recovered",
        expected_model=MODEL,
    )
    assert result.policy_file == actual / "d4_frozen_policy.json"
    assert result.source_kind == "DIRECTORY"


def test_resolver_recovers_valid_d4_package_from_repo_local_zip(tmp_path: Path):
    source = _write_valid_d4(tmp_path / "source")
    archive = tmp_path / "backup" / "d4-backup.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in source.iterdir():
            handle.write(path, arcname=f"archived-d4/{path.name}")
    for path in source.iterdir():
        path.unlink()
    source.rmdir()

    result = resolve_frozen_d4_evidence(
        preferred_root=tmp_path / "missing",
        search_roots=(tmp_path,),
        recovery_root=tmp_path / "recovered",
        expected_model=MODEL,
    )
    assert result.source_kind == "ZIP"
    assert result.source_path == archive
    assert result.policy_file.is_file()
    assert validate_d4_evidence_root(result.policy_file.parent, expected_model=MODEL).model_digest == DIGEST


def test_resolver_fails_closed_on_conflicting_completed_d4_results(tmp_path: Path):
    _write_valid_d4(tmp_path / "one", policy_id="DEFAULT", digest="sha256:digest-a")
    _write_valid_d4(tmp_path / "two", policy_id="THINK_OFF", digest="sha256:digest-b")
    with pytest.raises(ValueError, match="conflicting.*D4"):
        resolve_frozen_d4_evidence(
            preferred_root=tmp_path / "missing",
            search_roots=(tmp_path,),
            recovery_root=tmp_path / "recovered",
            expected_model=MODEL,
        )
