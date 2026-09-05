from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .hd_next1_preregistration import verify_sha256_manifest


def authorize_hd_next1_execution(prereg_root: str | Path, *, owner_approved: bool) -> dict[str, object]:
    root = Path(prereg_root)
    if owner_approved is not True:
        raise ValueError("explicit owner approval is required")
    if verify_sha256_manifest(root):
        raise ValueError("preregistration integrity check failed")
    adequacy = json.loads((root / "claim_adequacy_report.json").read_text(encoding="utf-8"))
    prereg_auth = json.loads((root / "physical_execution_authorization.json").read_text(encoding="utf-8"))
    if adequacy.get("ready_for_owner_authorization") is not True:
        raise ValueError("claim-space adequacy is not green")
    if prereg_auth.get("physical_execution_authorized") is not False:
        raise ValueError("immutable preregistration authorization artifact was mutated")
    if prereg_auth.get("authorized_experiment_id") != "HD-NEXT-1":
        raise ValueError("preregistration experiment scope mismatch")
    manifest_sha = hashlib.sha256((root / "SHA256SUMS.csv").read_bytes()).hexdigest()
    return {
        "authorization_kind": "HD_NEXT1_OWNER_EXECUTION_AUTHORIZATION",
        "authorized_experiment_id": "HD-NEXT-1",
        "physical_execution_authorized": True,
        "owner_approved": True,
        "preregistration_manifest_sha256": manifest_sha,
        "historical_fingerprint": prereg_auth.get("historical_fingerprint"),
    }


def validate_owner_authorization(prereg_root: str | Path, payload: dict[str, object]) -> None:
    root = Path(prereg_root)
    if payload.get("physical_execution_authorized") is not True or payload.get("owner_approved") is not True:
        raise ValueError("owner execution authorization is required")
    if payload.get("authorized_experiment_id") != "HD-NEXT-1":
        raise ValueError("owner authorization experiment mismatch")
    if verify_sha256_manifest(root):
        raise ValueError("preregistration integrity check failed")
    expected = hashlib.sha256((root / "SHA256SUMS.csv").read_bytes()).hexdigest()
    if payload.get("preregistration_manifest_sha256") != expected:
        raise ValueError("owner authorization is stale for this preregistration")
