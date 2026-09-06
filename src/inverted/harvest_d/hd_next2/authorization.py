"""Owner authorization bound to immutable preregistration bytes."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
from pathlib import Path
from typing import Any, Mapping

from .preregistration import FROZEN_INPUT_FILES, canonical_a0_payloads_for_commit


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str):
        raise ValueError(f"non-finite JSON constant: {value}")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=_reject_pairs,
    )
    if not isinstance(value, dict):
        raise ValueError("frozen JSON must contain an object")
    return value


def _verified_package(root: Path) -> tuple[str, str, str]:
    checksum = root / "SHA256SUMS.csv"
    manifest = root / "frozen_case_manifest.json"
    config = root / "config.json"
    try:
        with checksum.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["filename", "sha256"]:
                raise ValueError
            rows = list(reader)
        expected_names = set(FROZEN_INPUT_FILES)
        if {row["filename"] for row in rows} != expected_names or len(rows) != len(expected_names):
            raise ValueError
        parsed_config = _strict_json(config)
        parsed_manifest = _strict_json(manifest)
        commit = parsed_config.get("repo_commit")
        if not isinstance(commit, str):
            raise ValueError
        canonical = canonical_a0_payloads_for_commit(commit)
        for row in rows:
            frozen = root / row["filename"]
            name = row["filename"]
            if not frozen.is_file() or frozen.read_bytes() != canonical[name]:
                raise ValueError
            if _sha(frozen) != row["sha256"]:
                raise ValueError
        stage = parsed_manifest.get("stage_id")
        if stage != "2A-0":
            raise ValueError
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=("filename", "sha256"), lineterminator="\n")
        writer.writeheader()
        for name in FROZEN_INPUT_FILES:
            writer.writerow({"filename": name, "sha256": hashlib.sha256(canonical[name]).hexdigest()})
        if checksum.read_bytes() != buffer.getvalue().encode("utf-8"):
            raise ValueError
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("preregistration package integrity failure") from exc
    return stage, _sha(manifest), _sha(checksum)


def prepare_stage_authorization(package: str | Path) -> dict[str, Any]:
    """Prepare public package identity bytes for an owner to attest separately."""
    stage, manifest_hash, checksum_hash = _verified_package(Path(package))
    return {
        "stage_id": stage, "manifest_sha256": manifest_hash,
        "checksum_sha256": checksum_hash,
    }


def _owner_secret(secret: bytes) -> bytes:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("owner secret must be at least 32 explicitly supplied bytes")
    return secret


def _attested_bytes(payload: Mapping[str, Any]) -> bytes:
    bound = {
        "domain": "HD-NEXT-2A-OWNER-AUTHORIZATION-V1",
        "stage_id": payload.get("stage_id"),
        "manifest_sha256": payload.get("manifest_sha256"),
        "checksum_sha256": payload.get("checksum_sha256"),
        "owner_approved": payload.get("owner_approved"),
    }
    return json.dumps(bound, sort_keys=True, separators=(",", ":")).encode("utf-8")


def authorize_stage_execution(
    prepared_identity: Mapping[str, Any], *, owner_approved: bool, owner_secret: bytes,
) -> dict[str, Any]:
    """Create a detached HMAC owner attestation over prepared package identity."""
    expected_keys = {"stage_id", "manifest_sha256", "checksum_sha256"}
    if set(prepared_identity) != expected_keys:
        raise ValueError("prepared package identity is malformed")
    payload = {**dict(prepared_identity), "owner_approved": owner_approved is True}
    payload["owner_hmac_sha256"] = hmac.new(
        _owner_secret(owner_secret), _attested_bytes(payload), hashlib.sha256,
    ).hexdigest()
    return payload


def validate_stage_authorization(
    package: str | Path, authorization: Mapping[str, Any], *, owner_secret: bytes,
) -> dict[str, Any]:
    """Recompute all frozen hashes and validate the detached owner payload."""
    stage, manifest_hash, checksum_hash = _verified_package(Path(package))
    if set(authorization) != {
        "stage_id", "manifest_sha256", "checksum_sha256", "owner_approved", "owner_hmac_sha256",
    }:
        raise ValueError("owner authorization payload is malformed")
    if authorization.get("owner_approved") is not True:
        raise ValueError("owner authorization is not approved")
    expected_hmac = hmac.new(
        _owner_secret(owner_secret), _attested_bytes(authorization), hashlib.sha256,
    ).hexdigest()
    supplied_hmac = authorization.get("owner_hmac_sha256")
    if not isinstance(supplied_hmac, str) or not hmac.compare_digest(supplied_hmac, expected_hmac):
        raise ValueError("owner authorization HMAC is forged or altered")
    expected = {"stage_id": stage, "manifest_sha256": manifest_hash, "checksum_sha256": checksum_hash}
    if any(authorization.get(key) != value for key, value in expected.items()):
        raise ValueError("authorization is stale, forged, or bound to the wrong stage")
    return dict(authorization)
