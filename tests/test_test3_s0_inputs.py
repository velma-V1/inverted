from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from inverted.test3_s0_inputs import (
    SourceAvailability,
    discover_bundle_files,
    load_source_manifest,
    verify_evidence_bundle,
    verify_file_hash,
    write_source_manifest,
)
from inverted.test3_s0_types import EvidenceSource


def test_hash_mutation_is_detected(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text('{"x":1}\n', encoding="utf-8")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert verify_file_hash(p, digest)
    p.write_text('{"x":2}\n', encoding="utf-8")
    assert verify_file_hash(p, digest) is False


def test_missing_required_source_is_scientific_blocker(tmp_path: Path):
    status = SourceAvailability.from_path(tmp_path / "missing", required=True)
    assert status.available is False
    assert status.scientific_blocker is True


def test_bundle_integrity_records_unhashed_extras_and_rejects_traversal(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    data = bundle / "events.jsonl"
    data.write_text('{"task_id":"t1"}\n', encoding="utf-8")
    extra = bundle / "notes.txt"
    extra.write_text("metadata\n", encoding="utf-8")
    digest = hashlib.sha256(data.read_bytes()).hexdigest()
    with (bundle / "SHA256SUMS.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        writer.writerow({"path": "events.jsonl", "sha256": digest, "bytes": data.stat().st_size})
    result = verify_evidence_bundle(bundle, claims_complete=True)
    assert result.integrity_ok is True
    assert "notes.txt" in result.unhashed_extras
    assert "events.jsonl" in discover_bundle_files(bundle)

    with (bundle / "SHA256SUMS.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["../escape.txt", "0" * 64, 0])
    compromised = verify_evidence_bundle(bundle, claims_complete=True)
    assert compromised.integrity_ok is False
    assert any("traversal" in item.lower() for item in compromised.errors)


def test_manifest_roundtrip_preserves_source_metadata(tmp_path: Path):
    path = tmp_path / "manifest.json"
    sources = [EvidenceSource(
        source_id="test2-mf",
        source_class="test2_model_free",
        path="/evidence/test2-mf",
        required=True,
        bundle_sha256="abc",
        git_sha="def",
        run_id="run-1",
        evidence_tier="instrument",
        complete_claim=True,
        metadata={"artifact_id": 123},
    )]
    write_source_manifest(path, sources)
    loaded = load_source_manifest(path)
    assert loaded[0].source_id == "test2-mf"
    assert loaded[0].metadata["artifact_id"] == 123
