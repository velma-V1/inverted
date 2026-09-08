from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from inverted.test3_repo_evidence import materialize_repo_empirical_sources
from inverted.test3_s0_inputs import verify_evidence_bundle


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_outer_manifest(evidence: Path, rows: list[tuple[str, bytes]]) -> None:
    with (evidence / "FILES-SHA256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        for rel, data in rows:
            writer.writerow({"path": rel, "sha256": _sha(data), "bytes": len(data)})


def _write_fixture(tmp_path: Path) -> tuple[Path, bytes, bytes]:
    repo = tmp_path / "repo"
    evidence = repo / "evidence"
    test1 = evidence / "test1" / "run1"
    test2 = evidence / "test2" / "tier-a" / "run2"
    test1.mkdir(parents=True)
    test2.mkdir(parents=True)

    provenance = {
        "schema_version": 1,
        "sources": [
            {"source_id": "test1", "source_class": "test1", "repo_path": "evidence/test1/run1"},
            {"source_id": "test2-tier-a", "source_class": "test2_tier_a", "repo_path": "evidence/test2/tier-a/run2"},
            {
                "source_id": "test2-model-free", "source_class": "test2_model_free",
                "repo_path": None, "committed": False,
                "regeneration": "python -m inverted.test2_cli model-free",
            },
        ],
    }
    provenance_bytes = (json.dumps(provenance, indent=2) + "\n").encode()
    (evidence / "PROVENANCE.json").write_bytes(provenance_bytes)

    test1_payloads = {
        "trials.csv": b"task,ok\na,1\n",
        "events.jsonl": b'{"event":"x"}\n',
        "model_calls.jsonl": b'{"call":1}\n',
    }
    test1_manifest = b"path,sha256,bytes\n" + b"".join(
        f"{name},{_sha(data)},{len(data)}\n".encode()
        for name, data in test1_payloads.items()
    )
    for name, data in {**test1_payloads, "SHA256SUMS.csv": test1_manifest}.items():
        (test1 / name).write_bytes(data)

    # Simulate a privacy-sanitized committed Test2 payload.  The outer manifest
    # proves the sanitized bytes, while the historical inner wrapper still
    # describes the pre-sanitization bytes and must not be treated as current.
    original_private = b'{"user_path":"private-original"}\n'
    sanitized = b'{"user_path":"[REDACTED_USER_PROFILE]"}\n'
    index = b'{"run_id":"run2"}\n'
    stale_inner = (
        "path,sha256,bytes\n"
        f"00-MASTER-INDEX.json,{_sha(index)},{len(index)}\n"
        f"model_calls.jsonl,{_sha(original_private)},{len(original_private)}\n"
    ).encode()
    (test2 / "00-MASTER-INDEX.json").write_bytes(index)
    (test2 / "model_calls.jsonl").write_bytes(sanitized)
    (test2 / "SHA256SUMS.csv").write_bytes(stale_inner)

    outer_rows: list[tuple[str, bytes]] = [("PROVENANCE.json", provenance_bytes)]
    for root, prefix in ((test1, "test1/run1"), (test2, "test2/tier-a/run2")):
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            outer_rows.append((f"{prefix}/{path.relative_to(root).as_posix()}", path.read_bytes()))
    _write_outer_manifest(evidence, outer_rows)
    return evidence, stale_inner, sanitized


def test_materializer_rewraps_sanitized_source_without_weakening_integrity(tmp_path: Path) -> None:
    evidence, stale_inner, sanitized = _write_fixture(tmp_path)
    out = tmp_path / "rehydrated"

    paths, report = materialize_repo_empirical_sources(evidence, out)

    test2 = paths["test2-tier-a"]
    verification = verify_evidence_bundle(test2, claims_complete=True)
    assert verification.integrity_ok is True
    assert verification.mismatched_hashes == []
    assert (test2 / "model_calls.jsonl").read_bytes() == sanitized
    assert report["sanitized_rewrapped_sources"] == ["test2-tier-a"]

    preserved = out / "source-manifests" / "test2-tier-a-SHA256SUMS.csv"
    assert preserved.read_bytes() == stale_inner
    assert (test2 / "SHA256SUMS.csv").read_bytes() != stale_inner


def test_materializer_leaves_already_consistent_source_wrapper_unchanged(tmp_path: Path) -> None:
    evidence, _, _ = _write_fixture(tmp_path)
    original = evidence / "test1" / "run1" / "SHA256SUMS.csv"
    expected = original.read_bytes()

    paths, report = materialize_repo_empirical_sources(evidence, tmp_path / "rehydrated")

    assert (paths["test1"] / "SHA256SUMS.csv").read_bytes() == expected
    assert "test1" not in report["sanitized_rewrapped_sources"]
