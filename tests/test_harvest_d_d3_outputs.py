import csv
import json
from pathlib import Path

from inverted.harvest_d.d3_cli import main


MANDATORY_FILES = {
    "00-HARVEST-D-D3-MASTER-INDEX.json",
    "d3_preflight.json",
    "d3_system_events.jsonl",
    "d3_campaign_journal.jsonl",
    "d3_call_ledger.jsonl",
    "d3_raw_model_requests.jsonl",
    "d3_raw_model_responses.jsonl",
    "d3_normalized_model_calls.jsonl",
    "d3_information_packets.jsonl",
    "d3_information_field_lineage.jsonl",
    "d3_state_snapshots.jsonl",
    "d3_evidence_snapshots.jsonl",
    "d3_authority_snapshots.jsonl",
    "d3_assistance_events.jsonl",
    "d3_scheduler_events.jsonl",
    "d3_sequential_analysis_state.jsonl",
    "d3_operator_events.jsonl",
    "d3_component_manifest.jsonl",
    "d3_recovery_trajectories.jsonl",
    "d3_reproducibility_calibration.jsonl",
    "d3_edge_cases.jsonl",
    "d3_errors.jsonl",
    "d3_counterfactuals.jsonl",
    "d3_scores_raw.jsonl",
    "d3_scores_normalized.jsonl",
    "d3_runtime_telemetry.jsonl",
    "d3_case_lineage.jsonl",
    "d3_capture_field_matrix.jsonl",
    "d3_intervention_opportunities.jsonl",
    "d3_decision_opportunity_sets.jsonl",
    "d3_case_structural_features.jsonl",
    "d3_model_behavior_features.jsonl",
    "d3_decision_boundary_telemetry.jsonl",
    "d3_causal_claim_graph.jsonl",
    "d3_claim_evidence_edges.jsonl",
    "d3_uncovered_space.jsonl",
    "d3_evidence_saturation.jsonl",
    "d3_protocol_violations.jsonl",
    "d3_assumption_ledger.jsonl",
    "d3_environment_provenance.json",
    "d3_data_dictionary.json",
    "d3_capture_completeness.json",
    "d3_missingness_summary.json",
    "d3_coverage_matrix.json",
    "d3_reproducibility_calibration.json",
    "d3_data_value_audit.json",
    "d3_final_report.json",
    "d4_handoff.json",
    "SHA256SUMS.csv",
}


def _model_free(tmp_path: Path) -> None:
    assert main([
        "--config", "configs/harvest-d-d3.json",
        "--output", str(tmp_path),
        "--model-free",
    ]) == 0


def test_model_free_finalization_emits_every_normative_artifact_family(tmp_path):
    _model_free(tmp_path)
    names = {path.name for path in tmp_path.iterdir() if path.is_file()}
    assert MANDATORY_FILES <= names


def test_data_value_audit_answers_all_15_independent_completeness_questions(tmp_path):
    _model_free(tmp_path)
    audit = json.loads((tmp_path / "d3_data_value_audit.json").read_text(encoding="utf-8"))
    assert audit["overall_passed"] is True
    assert len(audit["checks"]) == 15
    assert {row["id"] for row in audit["checks"]} == {f"Q{i}" for i in range(1, 16)}
    assert all(row["passed"] for row in audit["checks"])


def test_zero_call_capture_completeness_is_explicit_not_ambiguous(tmp_path):
    _model_free(tmp_path)
    capture = json.loads((tmp_path / "d3_capture_completeness.json").read_text(encoding="utf-8"))
    missingness = json.loads((tmp_path / "d3_missingness_summary.json").read_text(encoding="utf-8"))
    assert capture == {
        "admissible_calls": 0,
        "capture_incomplete_calls": 0,
        "physical_model_calls": 0,
        "required_capture_rate": None,
    }
    assert missingness["zero_call_model_free"] is True
    assert missingness["reason_counts"]["NOT_APPLICABLE"] > 0


def test_checksum_manifest_covers_master_index_and_data_audit(tmp_path):
    _model_free(tmp_path)
    with (tmp_path / "SHA256SUMS.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    files = {row["file"] for row in rows}
    assert "00-HARVEST-D-D3-MASTER-INDEX.json" in files
    assert "d3_data_value_audit.json" in files
    assert "d4_handoff.json" in files
