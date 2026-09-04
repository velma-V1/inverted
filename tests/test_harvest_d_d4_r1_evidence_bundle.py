from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from inverted.harvest_d.d4_r1_evidence_bundle import build_d4_r1_evidence_bundle


QWEN_MODEL = "qwen3.5:9b-q8_0"
QWEN_DIGEST = "441ec31e4d2aedceb97dd834b036db104d943fbe3dbc1e5c8ac95eeaa9141c77"
SMALL_MODEL = "qwen2.5:1.5b-instruct-q8_0"
SMALL_DIGEST = "sha256:small-test-digest"
EXECUTION_COMMIT = "7504c277b23ad1c956fe309fbc48876f72537215"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_checksums(root: Path) -> None:
    manifest = root / "SHA256SUMS.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "file"])
        for path in sorted(p for p in root.iterdir() if p.is_file() and p.name != manifest.name):
            writer.writerow([_sha256(path), path.name])


def _write_d4(root: Path) -> Path:
    root.mkdir(parents=True)
    _write_json(root / "d4_frozen_policy.json", {
        "state": "FROZEN",
        "policy_id": "DEFAULT",
        "model_id": QWEN_MODEL,
        "model_digest": QWEN_DIGEST,
        "chat_options": {},
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
        "model_id": QWEN_MODEL,
        "model_digest": QWEN_DIGEST,
    })
    (root / "d4_call_ledger.jsonl").write_text(
        "".join(json.dumps({"experiment_id": f"D4:e{i:02d}", "attempt": 1, "committed": True}) + "\n" for i in range(48)),
        encoding="utf-8",
    )
    (root / "d4_normalized_model_calls.jsonl").write_text(
        "".join(json.dumps({"experiment_id": f"D4:e{i:02d}"}) + "\n" for i in range(48)),
        encoding="utf-8",
    )
    _write_checksums(root)
    return root


def _write_r1(root: Path, *, calls: int = 24, state: str = "R1_CALIBRATION_COMPLETE") -> Path:
    root.mkdir(parents=True)
    _write_json(root / "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json", {
        "protocol": "D3-CLOSURE-v2",
        "stage": "R1_CALIBRATION",
        "mode": "REAL_LOCAL",
        "final_state": state,
        "physical_model_calls": calls,
        "planned_physical_calls": 24,
        "max_physical_calls": 24,
        "infrastructure_failures": 0,
        "ready_for_test5": False,
        "blind_retries_allowed": False,
    })
    _write_json(root / "closure_r1_runtime_identity.json", {
        "SMALL_A": {"model_id": SMALL_MODEL, "model_digest": SMALL_DIGEST},
        "QWEN": {"model_id": QWEN_MODEL, "model_digest": QWEN_DIGEST},
    })
    _write_json(root / "closure_r1_readiness.json", {
        "protocol": "D3-CLOSURE-v2",
        "stage": "R1_CALIBRATION",
        "state": "R1_READY_FOR_PHYSICAL",
        "physical_model_calls": 0,
        "max_physical_calls": 24,
        "ready_for_physical_r1": True,
        "ready_for_test5": False,
    })
    _write_json(root / "closure_r1_plan.json", {
        "protocol": "D3-CLOSURE-v2",
        "stage": "R1_CALIBRATION",
        "planned_physical_calls": 24,
        "max_physical_calls": 24,
    })
    _write_json(root / "closure_reproducibility_calibration.json", {
        "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": "MEASURED", "physical_model_calls": calls,
    })
    _write_json(root / "closure_cost_calibration.json", {
        "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": "MEASURED", "physical_model_calls": calls,
    })
    ids = [f"R1:e{i:02d}" for i in range(calls)]
    (root / "closure_r1_call_ledger.jsonl").write_text(
        "".join(json.dumps({"experiment_id": exp, "attempt": 1, "committed": True, "completion_class": "SEMANTIC_RESULT"}) + "\n" for exp in ids),
        encoding="utf-8",
    )
    (root / "closure_r1_campaign_journal.jsonl").write_text(
        "".join(
            json.dumps({"experiment_id": exp, "state": state_name, "attempt": 1}) + "\n"
            for exp in ids for state_name in ("STARTED", "COMMITTED")
        ),
        encoding="utf-8",
    )
    (root / "closure_r1_normalized_calls.jsonl").write_text(
        "".join(json.dumps({"experiment_id": exp, "completion_class": "SEMANTIC_RESULT"}) + "\n" for exp in ids),
        encoding="utf-8",
    )
    for name in (
        "closure_r1_raw_model_requests.jsonl",
        "closure_r1_raw_model_responses.jsonl",
        "closure_r1_runtime_telemetry.jsonl",
    ):
        (root / name).write_text(
            "".join(json.dumps({"experiment_id": exp, "physical_model_call_id": f"r1-call:{exp}"}) + "\n" for exp in ids),
            encoding="utf-8",
        )
    _write_checksums(root)
    return root


def _tree_fingerprint(root: Path) -> dict[str, str]:
    return {path.name: _sha256(path) for path in sorted(root.iterdir()) if path.is_file()}


def test_bundle_preserves_valid_d4_and_complete_r1_without_mutating_sources(tmp_path: Path):
    d4 = _write_d4(tmp_path / "d4")
    r1 = _write_r1(tmp_path / "r1")
    before_d4 = _tree_fingerprint(d4)
    before_r1 = _tree_fingerprint(r1)

    result = build_d4_r1_evidence_bundle(
        d4_root=d4,
        r1_root=r1,
        output_root=tmp_path / "bundle",
        implementation_commit=EXECUTION_COMMIT,
        expected_qwen_model=QWEN_MODEL,
    )

    assert result["state"] == "EVIDENCE_BUNDLE_COMPLETE"
    assert result["r1_execution_commit"] == EXECUTION_COMMIT
    assert result["implementation_commit"] == EXECUTION_COMMIT  # compatibility alias
    assert result["d4"]["physical_model_calls"] == 48
    assert result["r1"]["physical_model_calls"] == 24
    assert result["r1"]["final_state"] == "R1_CALIBRATION_COMPLETE"
    index = (tmp_path / "bundle" / "00-HARVEST-D-D4-R1-EVIDENCE-INDEX.md").read_text(encoding="utf-8")
    assert "R1 execution commit" in index
    assert EXECUTION_COMMIT in index
    assert (tmp_path / "bundle" / "D4-COMPLETE-CAMPAIGN.zip").is_file()
    assert (tmp_path / "bundle" / "R1-CALIBRATION-CAMPAIGN.zip").is_file()
    assert (tmp_path / "bundle" / "SHA256SUMS-D4-R1-ARCHIVES.csv").is_file()
    assert (tmp_path / "bundle" / "evidence_provenance.json").is_file()
    assert _tree_fingerprint(d4) == before_d4
    assert _tree_fingerprint(r1) == before_r1


def test_bundle_accepts_real_partial_r1_and_labels_it_as_partial_evidence(tmp_path: Path):
    d4 = _write_d4(tmp_path / "d4")
    r1 = _write_r1(tmp_path / "r1", calls=7, state="R1_CALIBRATION_PARTIAL")

    result = build_d4_r1_evidence_bundle(
        d4_root=d4,
        r1_root=r1,
        output_root=tmp_path / "bundle",
        implementation_commit="abc123",
        expected_qwen_model=QWEN_MODEL,
    )

    assert result["r1"]["physical_model_calls"] == 7
    assert result["r1"]["final_state"] == "R1_CALIBRATION_PARTIAL"
    assert result["r1"]["evidence_class"] == "RAW_PERSISTED_REAL_LOCAL_PARTIAL"


def test_bundle_rejects_tampered_r1_before_archiving(tmp_path: Path):
    d4 = _write_d4(tmp_path / "d4")
    r1 = _write_r1(tmp_path / "r1")
    with (r1 / "closure_r1_normalized_calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")

    with pytest.raises(ValueError, match="checksum mismatch"):
        build_d4_r1_evidence_bundle(
            d4_root=d4,
            r1_root=r1,
            output_root=tmp_path / "bundle",
            implementation_commit="abc123",
            expected_qwen_model=QWEN_MODEL,
        )


def test_bundle_archives_are_deterministic_for_identical_sources(tmp_path: Path):
    d4 = _write_d4(tmp_path / "d4")
    r1 = _write_r1(tmp_path / "r1")
    first = build_d4_r1_evidence_bundle(
        d4_root=d4,
        r1_root=r1,
        output_root=tmp_path / "one",
        implementation_commit="abc123",
        expected_qwen_model=QWEN_MODEL,
    )
    second = build_d4_r1_evidence_bundle(
        d4_root=d4,
        r1_root=r1,
        output_root=tmp_path / "two",
        implementation_commit="abc123",
        expected_qwen_model=QWEN_MODEL,
    )

    assert first["archives"]["d4"]["sha256"] == second["archives"]["d4"]["sha256"]
    assert first["archives"]["r1"]["sha256"] == second["archives"]["r1"]["sha256"]
