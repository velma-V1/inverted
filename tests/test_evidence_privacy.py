from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from inverted.evidence_privacy import sanitize_tree, scan_tree


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_outer_manifest(root: Path, rel_paths: list[str]) -> Path:
    manifest = root / "FILES-SHA256.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        for rel in rel_paths:
            data = (root / rel).read_bytes()
            writer.writerow({"path": rel, "sha256": _sha(data), "bytes": len(data)})
    return manifest


def test_scan_reports_private_machine_paths_without_exposing_match_text(tmp_path: Path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    fake_user_a = "synthetic_alice"
    fake_user_b = "synthetic_bob"
    (evidence / "sample.json").write_text(
        json.dumps({
            "windows": f"C:/Users/{fake_user_a}/project/run.json",
            "linux": f"/home/{fake_user_b}/project/run.json",
            "safe": "configs/test3-s0.yaml",
        }),
        encoding="utf-8",
    )

    report = scan_tree(evidence)
    rendered = json.dumps(report, sort_keys=True)

    assert report["privacy_ok"] is False
    assert report["total_matches"] == 2
    assert report["categories"] == {"posix_home_profile": 1, "windows_user_profile": 1}
    assert fake_user_a not in rendered
    assert fake_user_b not in rendered
    assert report["files"][0]["path"] == "sample.json"
    assert "matches" not in report["files"][0]


def test_sanitize_tree_redacts_only_profile_prefix_reseals_outer_manifest_and_is_idempotent(tmp_path: Path):
    evidence = tmp_path / "evidence"
    run = evidence / "test2" / "tier-a" / "run"
    run.mkdir(parents=True)
    fake_user = "synthetic_private_user"
    metadata = run / "provenance.json"
    metadata.write_text(
        json.dumps({
            "cwd": f"C:\\Users\\{fake_user}\\inverted\\evidence",
            "output": f"/home/{fake_user}/inverted/output.json",
            "scientific_value": 17,
        }) + "\n",
        encoding="utf-8",
    )
    scientific = run / "effects.csv"
    scientific.write_text("metric,value\nscore,17\n", encoding="utf-8")
    binary = run / "opaque.bin"
    binary.write_bytes(b"\x00C:/Users/synthetic_binary_should_not_be_touched\x00")
    manifest = _write_outer_manifest(
        evidence,
        [
            "test2/tier-a/run/provenance.json",
            "test2/tier-a/run/effects.csv",
            "test2/tier-a/run/opaque.bin",
        ],
    )
    scientific_before = scientific.read_bytes()
    binary_before = binary.read_bytes()

    result = sanitize_tree(evidence, outer_manifest=manifest)
    sanitized = metadata.read_text(encoding="utf-8")
    rendered_result = json.dumps(result, sort_keys=True)

    assert result["privacy_ok"] is True
    assert result["files_changed"] == 1
    assert result["total_replacements"] == 2
    assert fake_user not in sanitized
    assert fake_user not in rendered_result
    assert "[REDACTED_USER_PROFILE]\\\\inverted\\\\evidence" in sanitized
    assert "[REDACTED_USER_PROFILE]/inverted/output.json" in sanitized
    assert scientific.read_bytes() == scientific_before
    assert binary.read_bytes() == binary_before

    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    row = next(item for item in rows if item["path"].endswith("provenance.json"))
    assert row["sha256"] == _sha(metadata.read_bytes())
    assert int(row["bytes"]) == len(metadata.read_bytes())

    before_second = manifest.read_bytes()
    second = sanitize_tree(evidence, outer_manifest=manifest)
    assert second["files_changed"] == 0
    assert second["total_replacements"] == 0
    assert manifest.read_bytes() == before_second


def test_scan_ignores_generated_privacy_reports_and_binary_files(tmp_path: Path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "PRIVACY-TRACKED-SCAN.json").write_text(
        '{"example":"C:/Users/synthetic_example_only"}\n', encoding="utf-8"
    )
    (evidence / "PRIVACY-TRANSFORM.json").write_text(
        '{"example":"/home/synthetic_example_only"}\n', encoding="utf-8"
    )
    (evidence / "binary.dat").write_bytes(b"\x00/home/synthetic_binary\x00")

    report = scan_tree(evidence)
    assert report["privacy_ok"] is True
    assert report["total_matches"] == 0
