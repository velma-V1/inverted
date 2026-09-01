import csv
import hashlib
import json
from pathlib import Path

from inverted.test3_repo_evidence import (
    load_repo_evidence,
    materialize_repo_empirical_sources,
    repo_s0_source_specs,
    verify_repo_evidence,
)


def test_committed_empirical_sources_are_complete_and_provenanced():
    root = Path(__file__).resolve().parents[1]
    evidence = load_repo_evidence(root / "evidence")

    assert evidence["schema_version"] == 1
    assert {row["source_id"] for row in evidence["sources"]} == {
        "test1",
        "test2-tier-a",
        "test2-model-free",
    }

    errors = verify_repo_evidence(root / "evidence", verify_hashes=False)
    assert errors == []

    test1 = next(row for row in evidence["sources"] if row["source_id"] == "test1")
    test2 = next(row for row in evidence["sources"] if row["source_id"] == "test2-tier-a")
    model_free = next(row for row in evidence["sources"] if row["source_id"] == "test2-model-free")

    assert (root / test1["repo_path"] / "SHA256SUMS.csv").is_file()
    assert (root / test1["repo_path"] / "trials.csv").is_file()
    assert (root / test1["repo_path"] / "events.jsonl").is_file()
    assert (root / test2["repo_path"] / "SHA256SUMS.csv").is_file()
    assert (root / test2["repo_path"] / "model_calls.jsonl").is_file()
    assert model_free["committed"] is False
    assert model_free["regeneration"]


def test_repo_source_specs_bind_exact_frozen_sources_and_generated_model_free(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    generated = tmp_path / "test2-model-free"
    generated.mkdir()

    specs = repo_s0_source_specs(root / "evidence", generated)

    assert [spec[0] for spec in specs] == ["test1", "test2-tier-a", "test2-model-free"]
    assert [spec[1] for spec in specs] == ["test1", "test2_tier_a", "test2_model_free"]
    assert specs[0][2].name == "decisive-20260831-054125-COMPLETE-DATA-PACKET"
    assert specs[1][2].name == "test2-local-20260831-213407-93922d"
    assert specs[2][2] == generated


def _write_git_normalized_fixture(tmp_path: Path) -> tuple[Path, dict[str, bytes]]:
    repo = tmp_path / "repo"
    evidence = repo / "evidence"
    test1 = evidence / "test1" / "run1"
    test2 = evidence / "test2" / "tier-a" / "run2"
    test1.mkdir(parents=True)
    test2.mkdir(parents=True)

    provenance = {
        "schema_version": 1,
        "sources": [
            {
                "source_id": "test1",
                "source_class": "test1",
                "repo_path": "evidence/test1/run1",
                "physical_model_evidence": True,
            },
            {
                "source_id": "test2-tier-a",
                "source_class": "test2_tier_a",
                "repo_path": "evidence/test2/tier-a/run2",
                "physical_model_evidence": True,
            },
            {
                "source_id": "test2-model-free",
                "source_class": "test2_model_free",
                "repo_path": None,
                "committed": False,
                "physical_model_evidence": False,
                "regeneration": "python -m inverted.test2_cli model-free",
            },
        ],
    }
    provenance_bytes = (json.dumps(provenance, indent=2) + "\n").encode("utf-8")
    (evidence / "PROVENANCE.json").write_bytes(provenance_bytes)

    originals: dict[str, bytes] = {
        "test1/run1/SHA256SUMS.csv": b"path,sha256,bytes\r\ntrials.csv,dummy,12\r\n",
        "test1/run1/trials.csv": b"task,ok\r\na,1\r\n",
        "test1/run1/events.jsonl": b'{"event":"x"}\r\n',
        "test1/run1/model_calls.jsonl": b'{"call":1}\r\n',
        "test2/tier-a/run2/SHA256SUMS.csv": b"path,sha256,bytes\r\nmodel_calls.jsonl,dummy,12\r\n",
        "test2/tier-a/run2/00-MASTER-INDEX.json": b'{\r\n  "run": "two"\r\n}\r\n',
        "test2/tier-a/run2/model_calls.jsonl": b'{"call":2}\r\n',
    }

    # Simulate what Git stores/checks out on Linux after Windows CRLF text was added:
    # CRLF becomes LF while the pre-commit evidence hash manifest still describes
    # the original Windows bytes.
    for rel, original in originals.items():
        canonical = original.replace(b"\r\n", b"\n")
        path = evidence / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical)

    rows = [
        {
            "path": "PROVENANCE.json",
            "sha256": hashlib.sha256(provenance_bytes).hexdigest(),
            "bytes": len(provenance_bytes),
        }
    ]
    for rel, original in originals.items():
        rows.append({
            "path": rel,
            "sha256": hashlib.sha256(original).hexdigest(),
            "bytes": len(original),
        })
    with (evidence / "FILES-SHA256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        writer.writerows(rows)

    return evidence, originals


def test_repo_verifier_accepts_only_provable_git_newline_canonicalization(tmp_path: Path):
    evidence, _ = _write_git_normalized_fixture(tmp_path)
    assert verify_repo_evidence(evidence, verify_hashes=True) == []


def test_repo_materializer_restores_original_empirical_bytes_before_s0(tmp_path: Path):
    evidence, originals = _write_git_normalized_fixture(tmp_path)
    out = tmp_path / "rehydrated"

    paths, report = materialize_repo_empirical_sources(evidence, out)

    assert set(paths) == {"test1", "test2-tier-a"}
    assert report["git_newline_rehydrated_files"] > 0
    assert report["unverified_files"] == []
    assert (paths["test1"] / "trials.csv").read_bytes() == originals["test1/run1/trials.csv"]
    assert (paths["test2-tier-a"] / "model_calls.jsonl").read_bytes() == originals[
        "test2/tier-a/run2/model_calls.jsonl"
    ]
