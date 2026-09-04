from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
from typing import Any, Iterable
import zipfile


_POLICY = "d4_frozen_policy.json"
_MASTER = "00-HARVEST-D-D4-QWEN-POLICY-MASTER-INDEX.json"
_IDENTITY = "d4_runtime_identity.json"
_LEDGER = "d4_call_ledger.jsonl"
_NORMALIZED = "d4_normalized_model_calls.jsonl"
_CHECKSUMS = "SHA256SUMS.csv"
_REQUIRED = (_POLICY, _MASTER, _IDENTITY, _LEDGER, _NORMALIZED, _CHECKSUMS)
_SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class FrozenD4Evidence:
    root: Path
    policy_file: Path
    source_kind: str
    source_path: Path
    model_id: str
    model_digest: str
    policy_id: str
    physical_model_calls: int
    fingerprint: str


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"{label} is unreadable: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} contains invalid JSONL: {path}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{label} contains a non-object row: {path}")
        rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_checksums(root: Path) -> None:
    manifest_path = root / _CHECKSUMS
    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError("D4 checksum manifest is unreadable") from exc
    if not rows or set(rows[0]) != {"sha256", "file"}:
        raise ValueError("D4 checksum manifest has an invalid schema")
    by_name = {str(row.get("file") or ""): row for row in rows}
    for required in _REQUIRED:
        if required == _CHECKSUMS:
            continue
        if required not in by_name:
            raise ValueError(f"D4 checksum manifest does not cover required artifact: {required}")
    for name, row in by_name.items():
        if not name or Path(name).name != name:
            raise ValueError("D4 checksum manifest contains a non-root artifact path")
        path = root / name
        if not path.is_file():
            raise ValueError(f"D4 checksum artifact is missing: {name}")
        if _sha256(path).lower() != str(row.get("sha256") or "").lower():
            raise ValueError(f"D4 checksum mismatch: {name}")


def validate_d4_evidence_root(root: str | Path, *, expected_model: str) -> FrozenD4Evidence:
    root = Path(root).resolve()
    missing = [name for name in _REQUIRED if not (root / name).is_file()]
    if missing:
        raise ValueError(f"D4 evidence package is incomplete; missing: {missing}")

    master = _read_json(root / _MASTER, "D4 master index")
    policy = _read_json(root / _POLICY, "D4 frozen policy")
    identity = _read_json(root / _IDENTITY, "D4 runtime identity")

    real_complete = (
        str(master.get("protocol")) == "D4-QWEN-POLICY-v1"
        and str(master.get("mode")) == "REAL_LOCAL"
        and int(master.get("physical_model_calls", -1)) == 48
        and int(master.get("planned_physical_calls", -1)) == 48
        and int(master.get("max_calls", -1)) == 48
        and str(master.get("final_state")) == "COMPLETE"
        and str(master.get("policy_state")) == "FROZEN"
        and master.get("blind_retries_allowed") is False
    )
    if not real_complete:
        raise ValueError("D4 evidence must be a REAL_LOCAL COMPLETE 48-call campaign with FROZEN policy")

    if str(policy.get("state")) != "FROZEN":
        raise ValueError("D4 policy is not FROZEN")
    model_id = str(policy.get("model_id") or "")
    model_digest = str(policy.get("model_digest") or "")
    if model_id != str(expected_model) or not model_digest:
        raise ValueError("D4 frozen policy model identity/digest is invalid")
    policy_id = str(policy.get("policy_id") or "")
    chat_options = policy.get("chat_options")
    if policy_id == "DEFAULT":
        if chat_options != {}:
            raise ValueError("D4 DEFAULT policy contains unexpected chat options")
    elif policy_id == "THINK_OFF":
        if chat_options != {"think": False}:
            raise ValueError("D4 THINK_OFF policy is not exactly think=false")
    else:
        raise ValueError("D4 frozen policy has an unsupported policy_id")
    if int(policy.get("matched_cases", 0)) < 24:
        raise ValueError("D4 frozen policy does not contain the required 24 matched cases")

    if (
        str(identity.get("protocol")) != "D4-QWEN-POLICY-v1"
        or str(identity.get("model_id")) != model_id
        or str(identity.get("model_digest")) != model_digest
    ):
        raise ValueError("D4 runtime identity does not match the frozen policy")

    ledger = _read_jsonl(root / _LEDGER, "D4 call ledger")
    normalized = _read_jsonl(root / _NORMALIZED, "D4 normalized calls")
    committed = [row for row in ledger if row.get("committed") is True]
    experiments = [str(row.get("experiment_id") or "") for row in committed]
    if len(ledger) != 48 or len(committed) != 48 or len(set(experiments)) != 48:
        raise ValueError("D4 evidence does not contain exactly 48 uniquely committed calls")
    if any(int(row.get("attempt", 0)) != 1 for row in committed):
        raise ValueError("D4 evidence contains a retried physical call")
    normalized_ids = {str(row.get("experiment_id") or "") for row in normalized}
    if len(normalized) != 48 or normalized_ids != set(experiments):
        raise ValueError("D4 normalized-call evidence does not match the 48-call ledger")

    _verify_checksums(root)
    fingerprint_payload = {
        "protocol": "D4-QWEN-POLICY-v1",
        "model_id": model_id,
        "model_digest": model_digest,
        "policy_id": policy_id,
        "chat_options": chat_options,
        "matched_cases": int(policy.get("matched_cases", 0)),
        "physical_model_calls": 48,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FrozenD4Evidence(
        root=root,
        policy_file=root / _POLICY,
        source_kind="DIRECTORY",
        source_path=root,
        model_id=model_id,
        model_digest=model_digest,
        policy_id=policy_id,
        physical_model_calls=48,
        fingerprint=fingerprint,
    )


def _walk_files(root: Path, filename: str) -> Iterable[Path]:
    if not root.exists():
        return ()
    matches: list[Path] = []
    for path in root.rglob(filename):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in _SKIP_DIRS for part in relative.parts):
            continue
        matches.append(path)
    return tuple(matches)


def _safe_zip_prefixes(archive: Path) -> tuple[str, ...]:
    try:
        with zipfile.ZipFile(archive) as handle:
            names = tuple(handle.namelist())
    except (OSError, zipfile.BadZipFile):
        return ()
    prefixes: set[str] = set()
    for name in names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or pure.name != _POLICY:
            continue
        prefix = str(pure.parent)
        if prefix == ".":
            prefix = ""
        required = {f"{prefix}/{item}".lstrip("/") for item in _REQUIRED}
        if required.issubset(set(names)):
            prefixes.add(prefix)
    return tuple(sorted(prefixes))


def _extract_zip_candidate(archive: Path, prefix: str, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as handle:
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or info.is_dir():
                continue
            parent = str(pure.parent)
            if parent != prefix:
                continue
            target = destination / pure.name
            target.write_bytes(handle.read(info))
    return destination


def resolve_frozen_d4_evidence(
    *,
    preferred_root: str | Path,
    search_roots: Iterable[str | Path],
    recovery_root: str | Path,
    expected_model: str,
) -> FrozenD4Evidence:
    preferred = Path(preferred_root).resolve()
    recovery = Path(recovery_root).resolve()
    roots = tuple(Path(root).resolve() for root in search_roots)
    candidates: list[FrozenD4Evidence] = []
    errors: list[str] = []
    seen_roots: set[Path] = set()

    directory_roots: list[Path] = []
    if preferred.exists():
        directory_roots.append(preferred)
    for search_root in roots:
        for policy_file in _walk_files(search_root, _POLICY):
            candidate_root = policy_file.parent.resolve()
            if candidate_root == recovery or recovery in candidate_root.parents:
                continue
            directory_roots.append(candidate_root)

    for root in directory_roots:
        if root in seen_roots:
            continue
        seen_roots.add(root)
        try:
            candidates.append(validate_d4_evidence_root(root, expected_model=expected_model))
        except ValueError as exc:
            errors.append(f"{root}: {exc}")

    zip_paths: set[Path] = set()
    for search_root in roots:
        for archive in _walk_files(search_root, "*.zip"):
            zip_paths.add(archive.resolve())
    # pathlib.rglob treats a literal wildcard as expected, but keep a direct
    # fallback for platforms/filesystems with unusual matching behavior.
    if not zip_paths:
        for search_root in roots:
            if not search_root.exists():
                continue
            for archive in search_root.rglob("*.zip"):
                try:
                    relative = archive.relative_to(search_root)
                except ValueError:
                    continue
                if any(part in _SKIP_DIRS for part in relative.parts):
                    continue
                zip_paths.add(archive.resolve())

    for archive in sorted(zip_paths):
        for prefix in _safe_zip_prefixes(archive):
            key = hashlib.sha256((str(archive) + "\0" + prefix).encode("utf-8")).hexdigest()[:16]
            extracted = _extract_zip_candidate(archive, prefix, recovery / key)
            try:
                evidence = validate_d4_evidence_root(extracted, expected_model=expected_model)
            except ValueError as exc:
                errors.append(f"{archive}!/{prefix}: {exc}")
                continue
            candidates.append(FrozenD4Evidence(
                root=evidence.root,
                policy_file=evidence.policy_file,
                source_kind="ZIP",
                source_path=archive,
                model_id=evidence.model_id,
                model_digest=evidence.model_digest,
                policy_id=evidence.policy_id,
                physical_model_calls=evidence.physical_model_calls,
                fingerprint=evidence.fingerprint,
            ))

    if not candidates:
        detail = "; ".join(errors[:8]) if errors else "no D4 policy/package candidates found"
        raise ValueError(f"no valid completed frozen D4 evidence found; {detail}")

    fingerprints = {candidate.fingerprint for candidate in candidates}
    if len(fingerprints) != 1:
        summary = ", ".join(
            f"{candidate.source_kind}:{candidate.source_path}:{candidate.policy_id}:{candidate.model_digest}"
            for candidate in candidates
        )
        raise ValueError(f"conflicting completed D4 evidence found; refuse ambiguous recovery: {summary}")

    preferred_candidates = [candidate for candidate in candidates if candidate.root == preferred]
    if preferred_candidates:
        return preferred_candidates[0]
    return sorted(candidates, key=lambda row: (row.source_kind != "DIRECTORY", str(row.source_path)))[0]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve an original completed Harvest-D D4 policy without rerunning D4")
    parser.add_argument("--preferred-root", required=True)
    parser.add_argument("--search-root", action="append", required=True)
    parser.add_argument("--recovery-root", required=True)
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evidence = resolve_frozen_d4_evidence(
            preferred_root=args.preferred_root,
            search_roots=args.search_root,
            recovery_root=args.recovery_root,
            expected_model=args.expected_model,
        )
        payload = {
            "state": "D4_EVIDENCE_RESOLVED",
            "policy_file": str(evidence.policy_file),
            "source_kind": evidence.source_kind,
            "source_path": str(evidence.source_path),
            "model_id": evidence.model_id,
            "model_digest": evidence.model_digest,
            "policy_id": evidence.policy_id,
            "physical_model_calls": evidence.physical_model_calls,
            "fingerprint": evidence.fingerprint,
            "d4_rerun_performed": False,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"D4 EVIDENCE RESOLUTION ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
