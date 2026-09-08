from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from inverted.test3_repo_evidence import materialize_repo_empirical_sources, verify_repo_evidence
from inverted.test3_s0_inputs import verify_evidence_bundle


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_manifest(path: Path, rows: list[tuple[str, bytes]]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["path,sha256,bytes\r\n"]
    for rel, data in rows:
        lines.append(f"{rel},{_sha(data)},{len(data)}\r\n")
    payload = "".join(lines).encode("utf-8")
    path.write_bytes(payload)
    return payload


def _privacy_transformed_repo(tmp_path: Path) -> tuple[Path, Path, bytes, bytes]:
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
                "source_id": "test2-model-free",
                "source_class": "test2_model_free",
                "repo_path": None,
                "committed": False,
                "regeneration": "python -m inverted.test2_cli model-free",
            },
        ],
    }
    provenance_bytes = (json.dumps(provenance, sort_keys=True) + "\n").encode()
    (evidence / "PROVENANCE.json").write_bytes(provenance_bytes)

    t1_trials = b"task,ok\r\na,1\r\n"
    t1_events = b'{"event":"x"}\r\n'
    t1_calls = b'{"call":1}\r\n'
    t1_manifest = _write_manifest(
        test1 / "SHA256SUMS.csv",
        [("trials.csv", t1_trials), ("events.jsonl", t1_events), ("model_calls.jsonl", t1_calls)],
    )
    (test1 / "trials.csv").write_bytes(t1_trials)
    (test1 / "events.jsonl").write_bytes(t1_events)
    (test1 / "model_calls.jsonl").write_bytes(t1_calls)

    master = b'{"run_id":"run2"}\n'
    calls = b'{"call":2}\n'
    original_private = b'{"cwd":"C:/private/profile"}\n'
    privacy_safe = b'{"cwd":"[REDACTED_USER_PROFILE]"}\n'
    stale_manifest = _write_manifest(
        test2 / "SHA256SUMS.csv",
        [
            ("00-MASTER-INDEX.json", master),
            ("model_calls.jsonl", calls),
            ("provenance.json", original_private),
        ],
    )
    (test2 / "00-MASTER-INDEX.json").write_bytes(master)
    (test2 / "model_calls.jsonl").write_bytes(calls)
    (test2 / "provenance.json").write_bytes(privacy_safe)

    outer_rows = [("PROVENANCE.json", provenance_bytes)]
    for root in (test1, test2):
        for item in sorted(p for p in root.rglob("*") if p.is_file()):
            outer_rows.append((item.relative_to(evidence).as_posix(), item.read_bytes()))
    with (evidence / "FILES-SHA256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        for rel, data in outer_rows:
            writer.writerow({"path": rel, "sha256": _sha(data), "bytes": len(data)})

    return evidence, test2, stale_manifest, privacy_safe


def test_outer_sealed_privacy_transform_is_resealed_only_in_temporary_s0_copy(tmp_path: Path):
    evidence, committed_test2, committed_inner_manifest, privacy_safe = _privacy_transformed_repo(tmp_path)
    assert verify_repo_evidence(evidence, verify_hashes=True) == []
    assert verify_evidence_bundle(committed_test2).integrity_ok is False

    paths, report = materialize_repo_empirical_sources(evidence, tmp_path / "rehydrated")

    normalized_test2 = paths["test2-tier-a"]
    assert verify_evidence_bundle(normalized_test2).integrity_ok is True
    assert (normalized_test2 / "provenance.json").read_bytes() == privacy_safe
    assert (committed_test2 / "SHA256SUMS.csv").read_bytes() == committed_inner_manifest
    assert (normalized_test2 / "SHA256SUMS.csv").read_bytes() != committed_inner_manifest
    assert report["integrity_resealed_sources"] == ["test2-tier-a"]
    reseal = report["integrity_reseals"][0]
    assert reseal["source_id"] == "test2-tier-a"
    assert reseal["reason"] == "outer_sealed_privacy_transform"
    assert reseal["outer_manifest_verified"] is True
    assert reseal["committed_source_mutated"] is False
