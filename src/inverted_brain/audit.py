from __future__ import annotations

import json
from pathlib import Path

from .config import CAMPAIGN_RUN_CEILING
from .evidence import verify_manifest


def audit_run(run_dir: Path, run_ceiling: int = CAMPAIGN_RUN_CEILING) -> dict:
    run_dir = Path(run_dir).resolve()
    problems: list[str] = []
    if not (run_dir / "sha256_manifest.json").exists():
        problems.append("missing_manifest")
        mismatches = []
    else:
        mismatches = verify_manifest(run_dir)
        if mismatches:
            problems.append("manifest_mismatch")
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8")) if (run_dir / "checkpoint.json").exists() else {}
    if checkpoint.get("agent_runs", 0) > run_ceiling:
        problems.append("run_ceiling_exceeded")
    if checkpoint.get("phase") != "complete":
        problems.append("campaign_not_complete")
    invalid = checkpoint.get("invalid_trials", [])
    valid = checkpoint.get("completed_trials", [])
    overlap = {(x.get("trial_id"),x.get("arm")) for x in invalid} & {(x.get("trial_id"),x.get("arm")) for x in valid}
    if overlap:
        problems.append("invalid_trial_in_valid_denominator")
    holdout = run_dir / "holdout_freeze.json"
    retention = run_dir / "retention_decision.json"
    if retention.exists() and not holdout.exists():
        problems.append("retention_without_frozen_holdout")
    return {"passed": not problems, "problems": problems, "manifest_mismatches": mismatches, "agent_runs": checkpoint.get("agent_runs",0)}
