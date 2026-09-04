from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from inverted.harvest_d.post_r1_data_dump import build_post_r1_data_dump


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_required(repo: Path, d4: Path) -> None:
    required_dirs = [
        "runs/harvest-d-d3-closure-r0-gate",
        "runs/harvest-d-d3-closure-r1-model-free-gate",
        "runs/harvest-d-d3-closure-r1",
        "runs/frozen-harvest-d-d3-20260903",
        "runs/post-d3-analysis-r1",
        "runs/evidence-publish/harvest-d-d4-r1-20260904",
    ]
    for i, rel in enumerate(required_dirs):
        _write(repo / rel / f"artifact-{i}.json", json.dumps({"i": i}) + "\n")
    _write(d4 / "d4_frozen_policy.json", '{"state":"FROZEN"}\n')
    _write(repo / "configs/harvest-d-d3-closure-v2.json", "{}\n")
    _write(repo / "scripts/run-harvest-d-d3-closure-r1.ps1", "Write-Host R1\n")
    _write(repo / "src/inverted/harvest_d/d3_closure_r1.py", "# r1\n")
    _write(repo / "docs/research/2026-09-04-inverted-complete-research-testing-brain-dossier.md", "# dossier\n")


def test_post_r1_dump_collects_required_evidence_provenance_inventory_and_hashes(tmp_path: Path):
    repo = tmp_path / "repo"
    d4 = tmp_path / "quarantine" / "harvest-d-d4-qwen-policy"
    _make_required(repo, d4)
    output = tmp_path / "out"

    result = build_post_r1_data_dump(
        repo_root=repo,
        d4_root=d4,
        output_root=output,
        r1_execution_commit="7504c277b23ad1c956fe309fbc48876f72537215",
        publisher_commit="2edcc735961bc485bac588a248315f6ee50d0e22",
        git_metadata={"branch": "fix/d3-closure-v2", "status": "clean", "log": "abc test"},
        source_archives=None,
    )

    assert result["state"] == "POST_R1_DATA_DUMP_COMPLETE"
    assert result["model_inference_performed"] is False
    assert result["source_mutation_observed"] is False
    assert Path(result["zip_path"]).is_file()
    assert Path(result["sha256_file"]).is_file()

    stage = Path(result["staging_root"])
    for name in (
        "PROVENANCE.json",
        "PROVENANCE.txt",
        "FILE_INVENTORY.csv",
        "SHA256_MANIFEST.csv",
        "DISCOVERED_SOURCE_ARTIFACTS.csv",
        "DATA_DUMP_INDEX.md",
    ):
        assert (stage / name).is_file(), name

    discovered = (stage / "DISCOVERED_SOURCE_ARTIFACTS.csv").read_text(encoding="utf-8")
    assert "harvest-d-d3-closure-r0-gate" in discovered
    assert "harvest-d-d3-closure-r1-model-free-gate" in discovered
    assert "harvest-d-d3-closure-r1" in discovered
    assert "frozen-harvest-d-d3-20260903" in discovered
    assert "post-d3-analysis-r1" in discovered
    assert "harvest-d-d4-r1-20260904" in discovered
    assert "d4_frozen_policy.json" in discovered

    with (stage / "SHA256_MANIFEST.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert any(row["file"] == "FILE_INVENTORY.csv" for row in rows)
    for row in rows:
        path = stage / row["file"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]

    with zipfile.ZipFile(result["zip_path"]) as archive:
        names = set(archive.namelist())
    assert any(name.endswith("PROVENANCE.json") for name in names)
    assert any("payload/r1-real/" in name for name in names)
    assert any("payload/d4-original/" in name for name in names)


def test_post_r1_dump_fails_closed_when_required_evidence_is_missing(tmp_path: Path):
    repo = tmp_path / "repo"
    d4 = tmp_path / "d4"
    _make_required(repo, d4)
    missing = repo / "runs/harvest-d-d3-closure-r1"
    for path in missing.rglob("*"):
        if path.is_file():
            path.unlink()
    missing.rmdir()

    with pytest.raises(ValueError, match="required evidence root is missing"):
        build_post_r1_data_dump(
            repo_root=repo,
            d4_root=d4,
            output_root=tmp_path / "out",
            r1_execution_commit="7504c277b23ad1c956fe309fbc48876f72537215",
            publisher_commit="2edcc735961bc485bac588a248315f6ee50d0e22",
            git_metadata={},
            source_archives=None,
        )


def test_post_r1_dump_rejects_nonempty_output_root(tmp_path: Path):
    repo = tmp_path / "repo"
    d4 = tmp_path / "d4"
    _make_required(repo, d4)
    output = tmp_path / "out"
    _write(output / "existing.txt", "do not overwrite\n")
    with pytest.raises(ValueError, match="append-only"):
        build_post_r1_data_dump(
            repo_root=repo,
            d4_root=d4,
            output_root=output,
            r1_execution_commit="7504c277b23ad1c956fe309fbc48876f72537215",
            publisher_commit="2edcc735961bc485bac588a248315f6ee50d0e22",
            git_metadata={},
            source_archives=None,
        )
