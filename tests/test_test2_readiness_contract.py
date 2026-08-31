from __future__ import annotations

from pathlib import Path

from inverted.models import MockModelAdapter
from inverted.test2_artifacts import Test2ArtifactWriter
from inverted.test2_cli import _local_evidence
from inverted.test2_local_impl import LOCAL_MODELS, run_local_campaign
from inverted.test2_metadata import enrich_test2_evidence
from inverted.test2_preregistration import PREREGISTRATION
from inverted.test2_readiness import finalize_test2_evidence


def _empty_evidence(trials: list[dict]):
    return {
        "master_index": {"mode": "local", "run_id": "readiness", "physical_model_calls": 0, "hard_call_limit": 480},
        "raw": {
            "trials": trials,
            "model_calls": [],
            "prompts": [],
            "responses": [],
            "candidates": [],
            "events": [],
            "validator_results": [],
            "repairs": [],
        },
        "effects": {},
        "order": {},
        "models": {},
        "thresholds": {},
        "provenance": {"config": {"local": {"models": list(LOCAL_MODELS)}}, "environment": {}, "git": {}, "models": {}},
    }


def _primary_rows(st_successes: int = 17, rr_successes: int = 6, physical_offset: int = 0):
    rows = []
    for i in range(18):
        model = LOCAL_MODELS[i % 3]
        task_id = f"t{i // 3}"
        rows.append({
            "phase": "repair_factorial", "role": "repairer", "model": model, "task_id": task_id,
            "evaluation_id": f"repair_factorial|{task_id}|structured|targeted",
            "feedback_style": "structured", "strategy": "targeted", "success": i < st_successes,
            "catastrophic": False, "call_identity": f"st-{i}", "cache_hit": False,
            "physical_call_number": physical_offset + 2 * i + 1,
        })
        rows.append({
            "phase": "repair_factorial", "role": "repairer", "model": model, "task_id": task_id,
            "evaluation_id": f"repair_factorial|{task_id}|raw|regenerate",
            "feedback_style": "raw", "strategy": "regenerate", "success": i < rr_successes,
            "catastrophic": False, "call_identity": f"rr-{i}", "cache_hit": False,
            "physical_call_number": physical_offset + 2 * i + 2,
        })
    return rows


def _screen_rows():
    conditions = (("raw", "regenerate"), ("raw", "targeted"), ("structured", "regenerate"), ("structured", "targeted"))
    rows = []
    for model_index, model in enumerate(LOCAL_MODELS):
        for case_index, (feedback, strategy) in enumerate(conditions):
            rows.append({
                "phase": "repair_screen", "role": "repairer", "model": model,
                "task_id": f"screen-{case_index}",
                "evaluation_id": f"repair_screen|screen-{case_index}|{feedback}|{strategy}",
                "feedback_style": feedback, "strategy": strategy,
                "success": model_index < 3, "preservation_rate": 1.0 if model_index < 3 else 0.0,
            })
    return rows


def _raw_calls_for_packet(records: list[dict]):
    calls = []
    for index, row in enumerate(records, start=1):
        if row.get("phase") == "repair_factorial":
            identity = row["call_identity"]
            number = row["physical_call_number"]
        else:
            identity = f"screen-call-{index}"
            number = index
        calls.append({
            "phase": row.get("phase"), "task_id": row.get("task_id"), "model": row.get("model"),
            "role": row.get("role"), "call_identity": identity, "cache_hit": False,
            "logical_call_index": number, "physical_call_number": number,
            "prompt": [{"role": "user", "content": "fixture"}], "response": "{}",
            "telemetry": {
                "model": row.get("model"), "role": row.get("role"), "call_identity": identity,
                "physical_call_number": number, "logical_call_index": number,
                "status_code": 200, "error_class": None, "error_message": None,
            },
        })
    return calls


def test_campaign_repair_factorial_rows_carry_boolean_catastrophic_telemetry():
    models = [MockModelAdapter(model=name) for name in LOCAL_MODELS]
    result = run_local_campaign(models, run_id="readiness-catastrophic", hard_limit=480)
    repair_rows = [row for row in result["records"] if row.get("phase") == "repair_factorial"]
    assert repair_rows
    assert all(isinstance(row.get("catastrophic"), bool) for row in repair_rows)


def test_contamination_audit_reports_duplicate_evaluation_model_even_when_last_row_is_progressive():
    duplicate = {
        "phase": "formalization", "role": "formalizer", "task_id": "f",
        "evaluation_id": "formalization|formalizer|f", "model": LOCAL_MODELS[0], "success": True,
    }
    trials = [dict(duplicate), dict(duplicate), {
        "phase": "progressive_holdout", "role": "pipeline", "task_id": "h",
        "evaluation_id": "progressive_holdout|pipeline|h|pipeline=S0", "pipeline": "S0",
        "model": "layered", "success": True, "runtime_allowed": True, "hidden_gold_success": True,
    }]
    evidence = _empty_evidence(trials)
    enrich_test2_evidence(evidence)
    collisions = evidence["diagnostics"]["contamination_audit"]["duplicate_evaluation_model_rows"]
    assert any(row["evaluation_id"] == duplicate["evaluation_id"] and row["model"] == duplicate["model"] for row in collisions)


def test_repair_factorial_matrix_coverage_uses_selected_three_model_cohort_not_all_five():
    selected = LOCAL_MODELS[:3]
    trials = []
    for evaluation_id in ("repair_factorial|r1", "repair_factorial|r2"):
        for model in selected:
            trials.append({
                "phase": "repair_factorial", "role": "repairer", "task_id": evaluation_id,
                "evaluation_id": evaluation_id, "model": model,
                "feedback_style": "structured", "strategy": "targeted", "success": True,
            })
    evidence = _empty_evidence(trials)
    enrich_test2_evidence(evidence)
    rows = [row for row in evidence["diagnostics"]["matrix_coverage"] if row["phase"] == "repair_factorial"]
    assert rows
    assert all(set(row["expected_models"]) == set(selected) for row in rows)
    assert all(row["missing_models"] == [] and row["matched_complete"] is True for row in rows)


def test_packet_finalization_embeds_frozen_preregistration_and_primary_verdict():
    stable_snapshot = {
        "before": {"server_version": "test", "models": {}},
        "after": {"server_version": "test", "models": {}},
        "identity_match": True,
    }
    screen = _screen_rows()
    primary = _primary_rows(physical_offset=len(screen))
    records = screen + primary
    raw_calls = _raw_calls_for_packet(records)
    local = {
        "records": records, "raw_calls": raw_calls, "physical_model_calls": len(raw_calls), "cache_hits": 0,
        "hard_call_limit": 480, "models": list(LOCAL_MODELS), "phase_limits": {}, "candidates": [],
        "events": [], "validator_results": [], "repairs": [], "ollama_provenance": stable_snapshot,
    }
    evidence = _local_evidence(local, {}, {"local": {"models": list(LOCAL_MODELS)}}, "readiness-verdict")
    finalize_test2_evidence(evidence)
    assert evidence["preregistration"] == PREREGISTRATION
    assert evidence["verdict"]["verdict"] == "SUPPORTED"
    assert evidence["verdict"]["material_contamination_blockers"] == []
    assert evidence["diagnostics"]["contamination_audit"]["physical_call_count_matches_master"] is True


def test_artifact_writer_emits_conventional_completion_proof_files(tmp_path):
    evidence = _empty_evidence(_primary_rows())
    run_dir = tmp_path / "proof"
    paths = Test2ArtifactWriter(run_dir).write_all(evidence)
    written = {str(Path(path).relative_to(run_dir)).replace("\\", "/") for path in paths.values()}
    required = {
        "events.jsonl", "model_calls.jsonl", "trials.csv", "trials.jsonl", "failures.csv",
        "summary.json", "summary.csv", "report.txt", "config.json", "provenance.json",
        "preregistration.json", "verdict.json", "SHA256SUMS.csv",
        "TEST2-NEXT-STRIDE-REPORT.txt", "TEST2-COMPLETE-EVIDENCE.txt",
    }
    assert required <= written
    master = (run_dir / "TEST2-COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    assert "preregistration.json" in master
    assert "verdict.json" in master
