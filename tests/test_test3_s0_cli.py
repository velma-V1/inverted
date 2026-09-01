from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from inverted.test3_s0_cli import _flatten_validator_results, _verify_sources, main
from inverted.test3_s0_normalize import normalize_test2_event
from inverted.test3_s0_types import EvidenceSource


def test_validate_instrument_accepts_partial_sources_and_emits_partial_verdict(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({
        "experiment": "test3-section0-github-causal-discovery",
        "mode": "model-free",
        "physical_model_call_ceiling": 0,
        "architecture_claims_authorized": False,
        "required_source_classes": ["test1", "test2_tier_a", "test2_model_free"],
        "allow_partial_instrument_validation": True,
    }), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": []}), encoding="utf-8")
    out = tmp_path / "out"
    rc = main(["validate-instrument", "--config", str(config), "--manifest", str(manifest), "--output-dir", str(out)])
    assert rc == 0
    verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["verdict"] == "PARTIAL_INPUT_EVIDENCE"
    assert verdict["physical_model_calls"] == 0


def test_run_refuses_missing_required_sources(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({
        "experiment": "test3-section0-github-causal-discovery",
        "mode": "model-free",
        "physical_model_call_ceiling": 0,
        "architecture_claims_authorized": False,
        "required_source_classes": ["test1"],
        "allow_partial_instrument_validation": True,
    }), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": []}), encoding="utf-8")
    rc = main(["run", "--config", str(config), "--manifest", str(manifest), "--output-dir", str(tmp_path / "out")])
    assert rc != 0


def test_cli_source_verification_blocks_manifest_identity_mismatch(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    provenance = bundle / "provenance.json"
    provenance.write_text(json.dumps({"git_sha": "observed-git", "run_id": "observed-run"}) + "\n", encoding="utf-8")
    digest = hashlib.sha256(provenance.read_bytes()).hexdigest()
    with (bundle / "SHA256SUMS.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        writer.writerow({"path": "provenance.json", "sha256": digest, "bytes": provenance.stat().st_size})
    source = EvidenceSource(
        source_id="tier-a",
        source_class="test2_tier_a",
        path=str(bundle),
        required=True,
        git_sha="expected-git",
        run_id="expected-run",
        complete_claim=True,
    )
    rows, details = _verify_sources([source])
    assert rows[0]["integrity_ok"] is False
    assert any("git_sha mismatch" in error for error in rows[0]["errors"])
    assert any("run_id mismatch" in error for error in rows[0]["errors"])
    assert len(details["tier-a"]["manifest_identity_errors"]) == 2


def test_validator_results_are_flattened_with_raw_disagreement_metadata():
    transition = normalize_test2_event("source", {
        "case_id": "t1",
        "component": "validator",
        "validator_results": [
            {"verifier": "schema", "result": "pass", "confidence": 1.0},
            {"verifier": "semantic", "result": "fail", "confidence": 0.62},
        ],
        "after_success": False,
    })
    rows = _flatten_validator_results([transition])
    assert len(rows) == 2
    assert rows[0]["task_id"] == "t1"
    assert {row["verifier"] for row in rows} == {"schema", "semantic"}
    assert {row["result"] for row in rows} == {"pass", "fail"}
    assert all("raw" in row for row in rows)


def test_cli_source_does_not_import_model_adapter():
    import inverted.test3_s0_cli as cli
    text = Path(cli.__file__).read_text(encoding="utf-8")
    assert "OllamaAdapter" not in text
    assert "run_local_campaign" not in text
    assert "from .models" not in text
