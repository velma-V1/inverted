from __future__ import annotations

import csv
import hashlib
import json
import shutil
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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _load_outer_hash_manifest(root: Path) -> tuple[list[dict[str, str]], list[str]]:
    manifest = root / "FILES-SHA256.csv"
    if not manifest.is_file():
        return [], [f"Missing outer evidence hash manifest: {manifest}"]
    try:
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
    except (OSError, csv.Error) as exc:
        return [], [f"Cannot read evidence hash manifest: {exc}"]
    if not rows:
        return [], ["FILES-SHA256.csv is empty"]
    return rows, []


def _validated_original_bytes(
    path: Path,
    *,
    expected_size: int,
    expected_sha256: str,
) -> tuple[bytes | None, str]:
    """Resolve bytes proven by the pre-commit hash manifest.

    Git commonly canonicalizes CRLF text to LF in repository blobs. We never
    accept that transformation by assumption. Exact checkout bytes are tried
    first; if they fail, a deterministic LF->CRLF reconstruction is accepted
    only when BOTH the original byte count and SHA-256 match the frozen
    pre-commit manifest exactly.
    """
    data = path.read_bytes()
    expected_hash = expected_sha256.lower()
    if len(data) == expected_size and _sha256_bytes(data).lower() == expected_hash:
        return data, "exact"

    # Only attempt text newline rehydration. NUL is a conservative binary guard.
    if b"\x00" not in data and b"\n" in data:
        normalized = data.replace(b"\r\n", b"\n")
        restored = normalized.replace(b"\n", b"\r\n")
        if len(restored) == expected_size and _sha256_bytes(restored).lower() == expected_hash:
            return restored, "git_lf_to_crlf_rehydrated"

    return None, "mismatch"


def _manifest_index(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], list[str]]:
    index: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for row in rows:
        rel = str(row.get("path") or "").replace("\\", "/")
        if not rel:
            errors.append("FILES-SHA256.csv contains a row without path")
            continue
        if rel in index:
            errors.append(f"Duplicate hash-manifest path: {rel}")
            continue
        index[rel] = row
    return index, errors


def verify_repo_evidence(
    evidence_root: str | Path,
    *,
    verify_hashes: bool = True,
) -> list[str]:
    """Return evidence contract failures without mutating source data.

    A Git LF-canonicalized checkout is valid only if the exact original Windows
    bytes can be reconstructed and proven against the frozen outer SHA-256
    manifest. No unproven normalization is accepted.
    """
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

    rows, manifest_errors = _load_outer_hash_manifest(root)
    errors.extend(manifest_errors)
    if manifest_errors:
        return errors
    index, index_errors = _manifest_index(rows)
    errors.extend(index_errors)

    for rel, row in index.items():
        path = root / Path(rel)
        if not path.is_file():
            errors.append(f"Hash-manifest file missing: {rel}")
            continue

        try:
            expected_size = int(str(row.get("bytes") or ""))
        except ValueError:
            errors.append(f"Invalid byte count in manifest: {rel}")
            continue
        expected_hash = str(row.get("sha256") or "").lower()
        if not expected_hash:
            errors.append(f"Missing SHA-256 in manifest: {rel}")
            continue

        _, mode = _validated_original_bytes(
            path,
            expected_size=expected_size,
            expected_sha256=expected_hash,
        )
        if mode == "mismatch":
            errors.append(f"Original-byte SHA-256 mismatch after Git newline recovery: {rel}")

    return errors


def materialize_repo_empirical_sources(
    evidence_root: str | Path,
    destination_root: str | Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Create byte-exact temporary copies of committed Test-1/Test-2 evidence.

    Source bytes are selected only when proven by evidence/FILES-SHA256.csv.
    This reverses Git newline canonicalization where the frozen hash proves the
    original CRLF form. The committed checkout itself is never modified.
    """
    root = Path(evidence_root)
    destination = Path(destination_root)
    provenance = load_repo_evidence(root)
    sources = _source_map(provenance)
    rows, manifest_errors = _load_outer_hash_manifest(root)
    if manifest_errors:
        raise ValueError("; ".join(manifest_errors))
    index, index_errors = _manifest_index(rows)
    if index_errors:
        raise ValueError("; ".join(index_errors))

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    file_report: list[dict[str, Any]] = []
    unverified: list[str] = []
    exact_count = 0
    rehydrated_count = 0

    for source_id in ("test1", "test2-tier-a"):
        source = sources.get(source_id)
        if not source or not source.get("repo_path"):
            raise ValueError(f"Missing committed source provenance for {source_id}")
        source_dir = root.parent / str(source["repo_path"])
        if not source_dir.is_dir():
            raise ValueError(f"Missing committed source directory: {source_dir}")

        target_dir = destination / source_id
        target_dir.mkdir(parents=True, exist_ok=True)
        paths[source_id] = target_dir

        for path in sorted(item for item in source_dir.rglob("*") if item.is_file()):
            rel_evidence = path.relative_to(root).as_posix()
            manifest_row = index.get(rel_evidence)
            if not manifest_row:
                unverified.append(rel_evidence)
                continue
            try:
                expected_size = int(str(manifest_row.get("bytes") or ""))
            except ValueError:
                unverified.append(rel_evidence)
                continue
            expected_hash = str(manifest_row.get("sha256") or "").lower()
            if not expected_hash:
                unverified.append(rel_evidence)
                continue

            original, mode = _validated_original_bytes(
                path,
                expected_size=expected_size,
                expected_sha256=expected_hash,
            )
            if original is None:
                unverified.append(rel_evidence)
                continue

            relative_source = path.relative_to(source_dir)
            target = target_dir / relative_source
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)

            if mode == "exact":
                exact_count += 1
            else:
                rehydrated_count += 1
            file_report.append({
                "source_id": source_id,
                "path": relative_source.as_posix(),
                "repo_path": rel_evidence,
                "verification_mode": mode,
                "sha256": expected_hash,
                "bytes": expected_size,
            })

    if unverified:
        raise ValueError(
            "Cannot materialize unverified repo evidence files: " + ", ".join(sorted(unverified))
        )

    report = {
        "verification_policy": "exact_bytes_or_hash_proven_git_lf_to_crlf_rehydration",
        "exact_files": exact_count,
        "git_newline_rehydrated_files": rehydrated_count,
        "unverified_files": [],
        "files": file_report,
    }
    return paths, report


def repo_s0_source_specs(
    evidence_root: str | Path,
    generated_model_free_path: str | Path,
    *,
    empirical_paths: dict[str, Path] | None = None,
) -> list[tuple[str, str, Path]]:
    """Resolve the exact frozen S0 source tuple list from repo provenance."""
    root = Path(evidence_root)
    provenance = load_repo_evidence(root)
    sources = _source_map(provenance)

    missing = [source_id for source_id in _REQUIRED_SOURCE_IDS if source_id not in sources]
    if missing:
        raise ValueError(f"Missing required source ids: {missing}")

    if empirical_paths is None:
        test1 = root.parent / str(sources["test1"].get("repo_path") or "")
        test2 = root.parent / str(sources["test2-tier-a"].get("repo_path") or "")
    else:
        if "test1" not in empirical_paths or "test2-tier-a" not in empirical_paths:
            raise ValueError("empirical_paths must contain test1 and test2-tier-a")
        test1 = Path(empirical_paths["test1"])
        test2 = Path(empirical_paths["test2-tier-a"])
    model_free = Path(generated_model_free_path)

    return [
        ("test1", "test1", test1),
        ("test2-tier-a", "test2_tier_a", test2),
        ("test2-model-free", "test2_model_free", model_free),
    ]
