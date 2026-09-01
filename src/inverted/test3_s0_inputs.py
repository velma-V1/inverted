from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .test3_s0_types import EvidenceSource


RECOGNIZED_FILES = {
    "00-MASTER-INDEX.json",
    "events.jsonl",
    "model_calls.jsonl",
    "trials.csv",
    "trials.jsonl",
    "failures.csv",
    "summary.json",
    "summary.csv",
    "report.txt",
    "config.json",
    "provenance.json",
    "preregistration.json",
    "verdict.json",
    "SHA256SUMS.csv",
    "COMPLETE-EVIDENCE.txt",
    "TEST2-COMPLETE-EVIDENCE.txt",
}


@dataclass(frozen=True)
class SourceAvailability:
    path: str
    required: bool
    available: bool
    scientific_blocker: bool
    reason: str | None = None

    @classmethod
    def from_path(cls, path: str | Path, required: bool) -> "SourceAvailability":
        p = Path(path)
        available = p.exists()
        return cls(
            path=str(p),
            required=required,
            available=available,
            scientific_blocker=bool(required and not available),
            reason=None if available else "source path does not exist",
        )


@dataclass
class BundleVerification:
    root: str
    integrity_ok: bool
    claims_complete: bool
    sha_inventory_present: bool
    hashed_files: list[dict[str, Any]] = field(default_factory=list)
    unhashed_extras: list[str] = field(default_factory=list)
    missing_hashed_files: list[str] = field(default_factory=list)
    mismatched_hashes: list[str] = field(default_factory=list)
    byte_mismatches: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_hash(path: str | Path, expected_sha256: str) -> bool:
    p = Path(path)
    return p.is_file() and _sha256(p).lower() == str(expected_sha256).lower()


def discover_bundle_files(root: str | Path) -> list[str]:
    base = Path(root)
    if not base.exists() or not base.is_dir():
        return []
    return sorted(
        path.relative_to(base).as_posix()
        for path in base.rglob("*")
        if path.is_file()
    )


def _safe_relative_path(root: Path, raw: str) -> tuple[Path | None, str | None]:
    if not raw:
        return None, "empty path in SHA256SUMS.csv"
    rel = Path(raw.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        return None, f"path traversal or absolute path rejected: {raw}"
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None, f"path traversal outside bundle rejected: {raw}"
    return candidate, None


def _load_json_if_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _extract_bundle_metadata(root: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for name in (
        "00-MASTER-INDEX.json",
        "provenance.json",
        "preregistration.json",
        "verdict.json",
        "summary.json",
        "config.json",
    ):
        path = root / name
        if path.is_file():
            metadata[name] = _load_json_if_mapping(path)
    index = metadata.get("00-MASTER-INDEX.json") or {}
    provenance = metadata.get("provenance.json") or {}
    git_section = provenance.get("git") if isinstance(provenance.get("git"), dict) else {}
    metadata["run_id"] = index.get("run_id") or provenance.get("run_id")
    metadata["git_sha"] = (
        provenance.get("git_sha")
        or provenance.get("git_commit")
        or git_section.get("commit")
        or git_section.get("sha")
    )
    metadata["physical_model_calls"] = index.get("physical_model_calls")
    metadata["mode"] = index.get("mode")
    metadata["file_count"] = len(discover_bundle_files(root))
    return metadata


def verify_evidence_bundle(root: str | Path, claims_complete: bool = True) -> BundleVerification:
    base = Path(root)
    if not base.exists() or not base.is_dir():
        return BundleVerification(
            root=str(base),
            integrity_ok=False,
            claims_complete=claims_complete,
            sha_inventory_present=False,
            errors=["bundle directory is missing"],
        )

    inventory = base / "SHA256SUMS.csv"
    result = BundleVerification(
        root=str(base),
        integrity_ok=True,
        claims_complete=claims_complete,
        sha_inventory_present=inventory.is_file(),
        metadata=_extract_bundle_metadata(base),
    )
    if claims_complete and not inventory.is_file():
        result.integrity_ok = False
        result.errors.append("complete evidence bundle is missing SHA256SUMS.csv")
        return result
    if not inventory.is_file():
        result.unhashed_extras = discover_bundle_files(base)
        return result

    hashed_paths: set[str] = set()
    try:
        with inventory.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "path" not in reader.fieldnames or "sha256" not in reader.fieldnames:
                result.integrity_ok = False
                result.errors.append("SHA256SUMS.csv must contain path and sha256 columns")
                return result
            for row_number, row in enumerate(reader, start=2):
                raw_path = str(row.get("path") or "")
                candidate, path_error = _safe_relative_path(base, raw_path)
                if path_error:
                    result.integrity_ok = False
                    result.errors.append(f"row {row_number}: {path_error}")
                    continue
                assert candidate is not None
                normalized = candidate.relative_to(base.resolve()).as_posix()
                hashed_paths.add(normalized)
                expected = str(row.get("sha256") or "").strip().lower()
                entry: dict[str, Any] = {
                    "path": normalized,
                    "expected_sha256": expected,
                    "expected_bytes": row.get("bytes"),
                    "exists": candidate.is_file(),
                }
                if not candidate.is_file():
                    result.integrity_ok = False
                    result.missing_hashed_files.append(normalized)
                    entry["status"] = "MISSING"
                    result.hashed_files.append(entry)
                    continue
                actual = _sha256(candidate)
                entry["actual_sha256"] = actual
                entry["actual_bytes"] = candidate.stat().st_size
                if actual != expected:
                    result.integrity_ok = False
                    result.mismatched_hashes.append(normalized)
                    entry["status"] = "HASH_MISMATCH"
                else:
                    entry["status"] = "OK"
                expected_bytes = row.get("bytes")
                if expected_bytes not in (None, ""):
                    try:
                        if int(expected_bytes) != candidate.stat().st_size:
                            result.integrity_ok = False
                            result.byte_mismatches.append(normalized)
                            entry["status"] = "BYTE_MISMATCH" if entry["status"] == "OK" else entry["status"]
                    except (TypeError, ValueError):
                        result.integrity_ok = False
                        result.errors.append(f"row {row_number}: invalid bytes value for {normalized}")
                result.hashed_files.append(entry)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        result.integrity_ok = False
        result.errors.append(f"could not parse SHA256SUMS.csv: {exc}")
        return result

    result.unhashed_extras = [
        path for path in discover_bundle_files(base)
        if path != "SHA256SUMS.csv" and path not in hashed_paths
    ]
    result.metadata["inventory_sha256"] = _sha256(inventory)
    result.metadata["hashed_file_count"] = len(result.hashed_files)
    result.metadata["unhashed_extra_count"] = len(result.unhashed_extras)
    return result


def verify_source_against_manifest(source: EvidenceSource, verification: BundleVerification) -> list[str]:
    """Verify immutable manifest identity fields against the observed bundle."""
    checks = (
        ("bundle_sha256", source.bundle_sha256, verification.metadata.get("inventory_sha256")),
        ("git_sha", source.git_sha, verification.metadata.get("git_sha")),
        ("run_id", source.run_id, verification.metadata.get("run_id")),
    )
    errors: list[str] = []
    for field_name, expected, observed in checks:
        if expected in (None, ""):
            continue
        if observed in (None, ""):
            errors.append(f"{field_name} expected {expected!r} but observed value is missing")
            continue
        if str(expected) != str(observed):
            errors.append(f"{field_name} mismatch: expected {expected!r}, observed {observed!r}")
    return errors


def _coerce_source(row: dict[str, Any]) -> EvidenceSource:
    allowed = {
        "source_id", "source_class", "path", "required", "bundle_sha256",
        "git_sha", "run_id", "evidence_tier", "complete_claim", "schema_version",
        "created_at", "metadata",
    }
    payload = {key: row.get(key) for key in allowed if key in row}
    payload.setdefault("required", False)
    payload.setdefault("metadata", {})
    if not isinstance(payload.get("metadata"), dict):
        payload["metadata"] = {"raw_metadata": payload.get("metadata")}
    return EvidenceSource(**payload)


def load_source_manifest(path: str | Path) -> list[EvidenceSource]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(value, dict):
        rows = value.get("sources", [])
    elif isinstance(value, list):
        rows = value
    else:
        raise ValueError("source manifest must be a JSON object or list")
    if not isinstance(rows, list):
        raise ValueError("source manifest sources must be a list")
    return [_coerce_source(dict(row)) for row in rows if isinstance(row, dict)]


def write_source_manifest(path: str | Path, sources: Iterable[EvidenceSource | dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for source in sources:
        rows.append(asdict(source) if isinstance(source, EvidenceSource) else dict(source))
    payload = {
        "schema": "test3-s0-source-manifest-v1",
        "sources": rows,
    }
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
