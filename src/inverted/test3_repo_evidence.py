from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


_REQUIRED_SOURCE_IDS = ("test1", "test2-tier-a", "test2-model-free")
_REQUIRED_FILES = {
    "test1": ("SHA256SUMS.csv", "trials.csv", "events.jsonl", "model_calls.jsonl"),
    "test2-tier-a": ("SHA256SUMS.csv", "00-MASTER-INDEX.json", "model_calls.jsonl"),
}


def load_repo_evidence(evidence_root: str | Path) -> dict[str, Any]:
    root = Path(evidence_root)
    path = root / "PROVENANCE.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing repo evidence provenance: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_map(provenance: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = provenance.get("sources")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        source_id = str(raw.get("source_id") or "")
        if source_id:
            out[source_id] = dict(raw)
    return out


def verify_repo_evidence(
    evidence_root: str | Path,
    *,
    verify_hashes: bool = True,
) -> list[str]:
    """Return evidence contract failures without mutating source data."""
    root = Path(evidence_root)
    errors: list[str] = []

    try:
        provenance = load_repo_evidence(root)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return [str(exc)]

    if provenance.get("schema_version") != 1:
        errors.append("PROVENANCE.json schema_version must be 1")

    sources = _source_map(provenance)
    missing_ids = [source_id for source_id in _REQUIRED_SOURCE_IDS if source_id not in sources]
    if missing_ids:
        errors.append(f"Missing provenance source ids: {missing_ids}")

    for source_id in ("test1", "test2-tier-a"):
        row = sources.get(source_id)
        if not row:
            continue
        repo_path = row.get("repo_path")
        if not repo_path:
            errors.append(f"{source_id} has no repo_path")
            continue
        # repo_path is repository-root-relative; evidence_root is repo/evidence.
        source_dir = root.parent / str(repo_path)
        if not source_dir.is_dir():
            errors.append(f"Missing committed source directory: {source_dir}")
            continue
        for name in _REQUIRED_FILES[source_id]:
            if not (source_dir / name).is_file():
                errors.append(f"Missing {source_id} required file: {name}")

    model_free = sources.get("test2-model-free")
    if model_free:
        if model_free.get("committed") is not False:
            errors.append("test2-model-free must remain marked committed=false")
        if not model_free.get("regeneration"):
            errors.append("test2-model-free is missing its regeneration command")

    if not verify_hashes:
        return errors

    manifest = root / "FILES-SHA256.csv"
    if not manifest.is_file():
        errors.append(f"Missing outer evidence hash manifest: {manifest}")
        return errors

    try:
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        errors.append(f"Cannot read evidence hash manifest: {exc}")
        return errors

    if not rows:
        errors.append("FILES-SHA256.csv is empty")
        return errors

    seen: set[str] = set()
    for row in rows:
        rel = str(row.get("path") or "").replace("\\", "/")
        if not rel:
            errors.append("FILES-SHA256.csv contains a row without path")
            continue
        if rel in seen:
            errors.append(f"Duplicate hash-manifest path: {rel}")
            continue
        seen.add(rel)
        path = root / Path(rel)
        if not path.is_file():
            errors.append(f"Hash-manifest file missing: {rel}")
            continue
        expected_size = str(row.get("bytes") or "")
        if expected_size:
            try:
                if path.stat().st_size != int(expected_size):
                    errors.append(f"Byte-size mismatch: {rel}")
                    continue
            except ValueError:
                errors.append(f"Invalid byte count in manifest: {rel}")
                continue
        expected_hash = str(row.get("sha256") or "").lower()
        if not expected_hash:
            errors.append(f"Missing SHA-256 in manifest: {rel}")
            continue
        if _sha256(path).lower() != expected_hash:
            errors.append(f"SHA-256 mismatch: {rel}")

    return errors


def repo_s0_source_specs(
    evidence_root: str | Path,
    generated_model_free_path: str | Path,
) -> list[tuple[str, str, Path]]:
    """Resolve the exact frozen S0 source tuple list from repo provenance."""
    root = Path(evidence_root)
    provenance = load_repo_evidence(root)
    sources = _source_map(provenance)

    missing = [source_id for source_id in _REQUIRED_SOURCE_IDS if source_id not in sources]
    if missing:
        raise ValueError(f"Missing required source ids: {missing}")

    test1 = root.parent / str(sources["test1"].get("repo_path") or "")
    test2 = root.parent / str(sources["test2-tier-a"].get("repo_path") or "")
    model_free = Path(generated_model_free_path)

    return [
        ("test1", "test1", test1),
        ("test2-tier-a", "test2_tier_a", test2),
        ("test2-model-free", "test2_model_free", model_free),
    ]
