from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from inverted.harvest_d.hd_next1_config import load_hd_next1_config
from inverted.harvest_d.hd_next1_preregistration import build_preregistration_package


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "harvest-d-hd-next-1.json"
REQUIRED = {
    "claim_space_manifest.json",
    "search_space_manifest.json",
    "candidate_pruning_ledger.jsonl",
    "coverage_report.json",
    "interaction_coverage.json",
    "uncovered_space.json",
    "frozen_case_manifest.json",
    "frozen_randomization_assignments.jsonl",
    "confirmation_resolution_policy.json",
    "cost_calibration_plan.json",
    "cost_budget_state.jsonl",
    "statistical_decision_rule.json",
    "claim_adequacy_report.json",
    "physical_execution_authorization.json",
    "SHA256SUMS.csv",
}


def _verify_manifest(root: Path) -> list[str]:
    bad = []
    with (root / "SHA256SUMS.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = root / row["path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != row["sha256"]:
                bad.append(row["path"])
    return bad


def test_preregistration_is_complete_integral_and_zero_call(tmp_path):
    cfg = load_hd_next1_config(CONFIG)
    summary = build_preregistration_package(REPO, tmp_path, cfg)
    assert summary.physical_model_calls == 0
    assert REQUIRED <= {p.name for p in tmp_path.iterdir()}
    assert _verify_manifest(tmp_path) == []
    adequacy = json.loads((tmp_path / "claim_adequacy_report.json").read_text())
    auth = json.loads((tmp_path / "physical_execution_authorization.json").read_text())
    assert adequacy["physical_model_calls"] == 0
    assert adequacy["ready_for_owner_authorization"] is True
    assert adequacy["max_fully_powered_zero_loss_cells"] == 1
    assert auth["physical_execution_authorized"] is False
    assert auth["owner_physical_execution_approval_required"] is True
    assert auth["authorized_experiment_id"] == "HD-NEXT-1"
