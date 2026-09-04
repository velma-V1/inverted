from __future__ import annotations

import csv
import json
from pathlib import Path

from inverted.harvest_d.d3_closure_campaign import D3ClosureCampaign


_REQUIRED_R0 = {
    "closure_claim_space_manifest.json",
    "closure_search_space_manifest.json",
    "closure_candidate_equivalence_classes.jsonl",
    "closure_candidate_pruning_ledger.jsonl",
    "closure_prior_evidence_ledger.jsonl",
    "closure_treatment_catalog.jsonl",
    "closure_treatment_exposure.jsonl",
    "closure_pre_state_catalog.jsonl",
    "closure_action_frontier_catalog.jsonl",
    "closure_combinatorial_coverage.json",
    "closure_interaction_coverage.json",
    "closure_uncovered_space.json",
    "closure_r0_readiness_report.json",
    "closure_claim_adequacy_report.json",
}


def _config() -> dict:
    return json.loads(Path("configs/harvest-d-d3-closure-v2.json").read_text(encoding="utf-8"))


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_model_free_closure_emits_full_r0_package_without_changing_legacy_terminal_state(tmp_path: Path):
    result = D3ClosureCampaign(tmp_path, config=_config()).run_model_free()

    assert result.final_state == "MODEL_FREE_COMPLETE"
    assert result.physical_model_calls == 0
    assert _REQUIRED_R0 <= {path.name for path in tmp_path.iterdir() if path.is_file()}

    readiness = _read(tmp_path / "closure_r0_readiness_report.json")
    adequacy = _read(tmp_path / "closure_claim_adequacy_report.json")
    master = _read(tmp_path / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json")

    assert readiness["final_state"] == "R0_MODEL_FREE_COMPLETE"
    assert readiness["r0_ready"] is True
    assert readiness["physical_model_calls"] == 0
    assert readiness["historical_prior_fresh_observation_count"] == 0
    assert adequacy["physical_execution_authorized"] is False
    assert master["final_state"] == "MODEL_FREE_COMPLETE"
    assert master["physical_model_calls"] == 0
    assert master["r0_state"] == "R0_MODEL_FREE_COMPLETE"
    assert master["r0_readiness"] is True
    assert master["physical_execution_authorized"] is False


def test_model_free_finalization_checksums_every_r0_artifact(tmp_path: Path):
    D3ClosureCampaign(tmp_path, config=_config()).run_model_free()

    with (tmp_path / "SHA256SUMS.csv").open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    checksummed = {row["file"] for row in rows}

    assert _REQUIRED_R0 <= checksummed


def test_model_free_r0_package_does_not_make_test5_ready(tmp_path: Path):
    D3ClosureCampaign(tmp_path, config=_config()).run_model_free()

    handoff = _read(tmp_path / "test5_handoff.json")
    final = _read(tmp_path / "closure_final_report.json")

    assert handoff["ready_for_test5"] is False
    assert final["scientific_complete"] is False
    assert final["physical_model_calls"] == 0
    assert final["r0_state"] == "R0_MODEL_FREE_COMPLETE"
    assert final["physical_execution_authorized"] is False
