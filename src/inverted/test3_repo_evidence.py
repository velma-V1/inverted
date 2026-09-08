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


def _inner_manifest_mismatches(source_dir: Path) -> list[str]:
    """Return hash-stale entries, while rejecting malformed or incomplete wrappers.

    The caller has already proven every materialized payload byte against the
    frozen outer manifest.  Re-wrapping is therefore allowed only when the
    historical inner manifest is structurally valid and its referenced files
    exist, but one or more recorded hashes/byte counts describe older bytes.
    """
    inventory = source_dir / "SHA256SUMS.csv"
    if not inventory.is_file():
        raise ValueError(f"materialized source is missing SHA256SUMS.csv: {source_dir}")
    try:
        with inventory.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "path" not in reader.fieldnames or "sha256" not in reader.fieldnames:
                raise ValueError(f"malformed source SHA256SUMS.csv: {source_dir}")
            rows = [dict(row) for row in reader]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"cannot parse source SHA256SUMS.csv: {source_dir}: {exc}") from exc
    if not rows:
        raise ValueError(f"source SHA256SUMS.csv is empty: {source_dir}")

    root = source_dir.resolve()
    mismatches: list[str] = []
    seen: set[str] = set()
    for number, row in enumerate(rows, start=2):
        raw = str(row.get("path") or "").replace("\\", "/")
        rel = Path(raw)
        if not raw or rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"row {number}: invalid source manifest path {raw!r}")
        normalized = rel.as_posix()
        if normalized in seen:
            raise ValueError(f"row {number}: duplicate source manifest path {normalized}")
        seen.add(normalized)
        candidate = (source_dir / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"row {number}: source manifest path escapes bundle: {normalized}") from exc
        if not candidate.is_file():
            raise ValueError(f"row {number}: source manifest file is missing: {normalized}")

        expected = str(row.get("sha256") or "").strip().lower()
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise ValueError(f"row {number}: invalid source SHA-256 for {normalized}")
        stale = _sha256(candidate).lower() != expected
        expected_bytes = row.get("bytes")
        if expected_bytes not in (None, ""):
            try:
                stale = stale or int(str(expected_bytes)) != candidate.stat().st_size
            except ValueError as exc:
                raise ValueError(f"row {number}: invalid source byte count for {normalized}") from exc
        if stale:
            mismatches.append(normalized)
    return mismatches


def _write_current_source_wrapper(source_dir: Path) -> None:
    inventory = source_dir / "SHA256SUMS.csv"
    files = sorted(
        path for path in source_dir.rglob("*")
        if path.is_file() and path.resolve() != inventory.resolve()
    )
    if not files:
        raise ValueError(f"cannot re-wrap empty evidence source: {source_dir}")
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n"
        )
        writer.writeheader()
        for path in files:
            writer.writerow({
                "path": path.relative_to(source_dir).as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            })


def _rewrap_hash_stale_source(
    source_id: str,
    source_dir: Path,
    destination: Path,
) -> str | None:
    mismatches = _inner_manifest_mismatches(source_dir)
    if not mismatches:
        return None

    inventory = source_dir / "SHA256SUMS.csv"
    preserved_root = destination / "source-manifests"
    preserved_root.mkdir(parents=True, exist_ok=True)
    preserved = preserved_root / f"{source_id}-SHA256SUMS.csv"
    preserved.write_bytes(inventory.read_bytes())

    _write_current_source_wrapper(source_dir)
    residual = _inner_manifest_mismatches(source_dir)
    if residual:
        raise ValueError(
            f"temporary sanitized source wrapper failed verification for {source_id}: {residual}"
        )
    return preserved.relative_to(destination).as_posix()


def materialize_repo_empirical_sources(
    evidence_root: str | Path,
    destination_root: str | Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Materialize outer-manifest-proven Test-1/Test-2 evidence for S0.

    Every payload byte is selected only when proven by evidence/FILES-SHA256.csv.
    Git newline canonicalization is reversed only when the frozen hash proves
    the exact original bytes.  If privacy sanitization made a historical inner
    SHA wrapper stale, that wrapper is preserved outside the replay bundle and
    a temporary wrapper is generated over the already-proven sanitized bytes.
    The committed checkout itself is never modified.
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

    rewrapped_sources: list[str] = []
    preserved_source_manifests: dict[str, str] = {}
    for source_id in ("test1", "test2-tier-a"):
        preserved = _rewrap_hash_stale_source(source_id, paths[source_id], destination)
        if preserved is not None:
            rewrapped_sources.append(source_id)
            preserved_source_manifests[source_id] = preserved

    report = {
        "verification_policy": "exact_bytes_or_hash_proven_git_lf_to_crlf_rehydration",
        "sanitized_rewrap_policy": (
            "outer_manifest_proven_payload_only; structurally_valid_hash_stale_inner_wrapper_preserved"
        ),
        "exact_files": exact_count,
        "git_newline_rehydrated_files": rehydrated_count,
        "sanitized_rewrapped_sources": rewrapped_sources,
        "preserved_source_manifests": preserved_source_manifests,
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