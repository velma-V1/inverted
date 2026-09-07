from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_campaign_report(root: str | Path, policy: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    evidence_hashes = {
        "manifest": _file_sha256(path / "protocol-v2-manifest.json"),
        "observations": _file_sha256(path / "atomic_observations.jsonl"),
        "raw_calls": _file_sha256(path / "raw_calls.jsonl"),
        "task_pool": _file_sha256(path / "task-pool-v2.json"),
    }
    surface = {
        "protocol_version": 2,
        "policy": policy,
        "evidence_hashes": evidence_hashes,
    }
    (path / "operating-surface.json").write_text(
        json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Universal Tuning V2 Report",
        "",
        f"Status: {summary.get('status', 'UNKNOWN')}",
        f"Physical calls: {summary.get('physical_calls', 0)}",
        f"Atomic observations: {summary.get('observation_count', 0)}",
        "",
        "## Family Results",
        "",
    ]
    for family, item in policy.items():
        lines.extend([
            f"### {family}",
            f"- mode: {item.get('mode')}",
            f"- status: {item.get('status')}",
            f"- direct semantic: {item.get('direct_semantic')}",
            f"- thinking semantic: {item.get('thinking_semantic')}",
            f"- minimum useful budget: {item.get('minimum_useful_budget')}",
            f"- temperature: {json.dumps(item.get('temperature'), sort_keys=True)}",
            f"- holdout atomic: {item.get('holdout_atomic', 0)}",
            "",
        ])
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return surface
