from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any, Mapping

from .d3_config import D3Phase
from .d3_planner import D3ExperimentPlanner
from .d3_store import D3EvidenceStore


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _data_dictionary() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "layers": {
            "RAW_IMMUTABLE": [
                "d3_raw_model_requests.jsonl",
                "d3_raw_model_responses.jsonl",
                "d3_system_events.jsonl",
                "d3_state_snapshots.jsonl",
                "d3_evidence_snapshots.jsonl",
                "d3_authority_snapshots.jsonl",
            ],
            "NORMALIZED_QUERYABLE": [
                "d3_normalized_model_calls.jsonl",
                "d3_information_packets.jsonl",
                "d3_information_field_lineage.jsonl",
                "d3_scheduler_events.jsonl",
                "d3_assistance_events.jsonl",
                "d3_runtime_telemetry.jsonl",
                "d3_case_lineage.jsonl",
            ],
            "DERIVED_RECOMPUTABLE": [
                "d3_scores_raw.jsonl",
                "d3_scores_normalized.jsonl",
                "d3_counterfactuals.jsonl",
                "d3_sequential_analysis_state.jsonl",
                "d3_causal_claim_graph.jsonl",
                "d3_claim_evidence_edges.jsonl",
                "d3_coverage_matrix.json",
                "d3_data_value_audit.json",
            ],
        },
        "identity_key": "physical_model_call_id",
        "missingness_reason_codes": [
            "NOT_APPLICABLE",
            "NOT_EXPOSED_BY_RUNTIME",
            "COLLECTION_FAILED",
            "COLLECTION_SKIPPED_TO_AVOID_PERTURBATION",
            "REDACTED_FOR_SAFETY/SECRET_PROTECTION",
            "UNKNOWN",
            "CAPTURE_INCOMPLETE",
            "NOT_PREVIOUSLY_COLLECTED",
        ],
        "inference_retry_policy": "NO_BLIND_RETRY",
        "oracle_visibility": "SYSTEM_ONLY_POST_RESPONSE",
        "counterfactual_policy": "DETERMINISTIC_ZERO_CALL_WHERE_CAUSALLY_VALID",
    }


def _coverage(planner: D3ExperimentPlanner, root: Path) -> dict[str, Any]:
    observed = _jsonl_rows(root / "d3_scheduler_events.jsonl")
    observed_by_phase: dict[str, int] = {}
    observed_by_model: dict[str, int] = {}
    for row in observed:
        phase = str(row.get("phase", "UNKNOWN"))
        model = str(row.get("model_key", "UNKNOWN"))
        observed_by_phase[phase] = observed_by_phase.get(phase, 0) + 1
        observed_by_model[model] = observed_by_model.get(model, 0) + 1
    return {
        "schema_version": 1,
        "candidate_count": planner.candidate_count(),
        "candidate_by_phase": {
            phase.value: len(planner.candidates_for_phase(phase)) for phase in D3Phase
        },
        "candidate_by_model": {
            key: sum(
                1
                for phase in D3Phase
                for item in planner.candidates_for_phase(phase)
                if item.model_key == key
            )
            for key in planner.model_keys
        },
        "observed_by_phase": dict(sorted(observed_by_phase.items())),
        "observed_by_model": dict(sorted(observed_by_model.items())),
        "uncovered_reason_when_zero_call": "MODEL_FREE_SCHEMA_VALIDATION_ONLY",
    }


def _capture_completeness(root: Path) -> dict[str, Any]:
    rows = _jsonl_rows(root / "d3_call_ledger.jsonl")
    calls = len(rows)
    incomplete = sum(1 for row in rows if not bool(row.get("capture_complete", False)))
    admissible = sum(1 for row in rows if row.get("admissibility") == "ADMISSIBLE")
    return {
        "admissible_calls": admissible,
        "capture_incomplete_calls": incomplete,
        "physical_model_calls": calls,
        "required_capture_rate": None if calls == 0 else (calls - incomplete) / calls,
    }


def _missingness_summary(root: Path) -> dict[str, Any]:
    calls = _jsonl_count(root / "d3_call_ledger.jsonl")
    if calls == 0:
        return {
            "zero_call_model_free": True,
            "reason_counts": {
                "NOT_APPLICABLE": 8,
                "NOT_EXPOSED_BY_RUNTIME": 0,
                "COLLECTION_FAILED": 0,
                "COLLECTION_SKIPPED_TO_AVOID_PERTURBATION": 0,
                "REDACTED_FOR_SAFETY/SECRET_PROTECTION": 0,
                "UNKNOWN": 0,
                "CAPTURE_INCOMPLETE": 0,
                "NOT_PREVIOUSLY_COLLECTED": 0,
            },
        }
    matrix = _jsonl_rows(root / "d3_capture_field_matrix.jsonl")
    missing = sum(1 for row in matrix if not bool(row.get("present", False)))
    return {
        "zero_call_model_free": False,
        "reason_counts": {
            "NOT_APPLICABLE": 0,
            "NOT_EXPOSED_BY_RUNTIME": 0,
            "COLLECTION_FAILED": 0,
            "COLLECTION_SKIPPED_TO_AVOID_PERTURBATION": 0,
            "REDACTED_FOR_SAFETY/SECRET_PROTECTION": 0,
            "UNKNOWN": missing,
            "CAPTURE_INCOMPLETE": sum(
                1
                for row in _jsonl_rows(root / "d3_call_ledger.jsonl")
                if not bool(row.get("capture_complete", False))
            ),
            "NOT_PREVIOUSLY_COLLECTED": 0,
        },
    }


def _reproducibility_summary(root: Path, *, model_free: bool) -> dict[str, Any]:
    rows = _jsonl_rows(root / "d3_reproducibility_calibration.jsonl")
    return {
        "status": "NOT_RUN_MODEL_FREE" if model_free and not rows else ("RECORDED" if rows else "NOT_RUN"),
        "physical_calls": len(rows),
        "observations": len(rows),
        "model_free": model_free,
    }


def _environment_provenance(config: Mapping[str, Any], *, model_free: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "python": platform.python_version(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "safe_environment_only": True,
        "secrets_or_environment_variables_captured": False,
        "models": dict(config.get("models", {})),
        "generation_options": dict(config.get("generation_options", {})),
    }


def _audit_checks(root: Path, *, model_free: bool) -> list[dict[str, Any]]:
    questions = (
        ("Q1", "Can reconstruct why each physical call was scheduled?", ("d3_scheduler_events.jsonl",)),
        ("Q2", "Can reconstruct eligible alternatives and selection propensity?", ("d3_scheduler_events.jsonl", "d3_decision_opportunity_sets.jsonl")),
        ("Q3", "Can reconstruct model-visible versus system-known information?", ("d3_information_packets.jsonl", "d3_state_snapshots.jsonl")),
        ("Q4", "Can reconstruct information transformations, omissions, ordering and timing?", ("d3_information_field_lineage.jsonl", "d3_information_packets.jsonl")),
        ("Q5", "Can reconstruct unchosen mechanisms, actions and recovery opportunities?", ("d3_intervention_opportunities.jsonl", "d3_decision_opportunity_sets.jsonl")),
        ("Q6", "Can reconstruct deterministic rules, scores and decision-boundary telemetry?", ("d3_decision_boundary_telemetry.jsonl", "d3_component_manifest.jsonl")),
        ("Q7", "Can replay deterministic OFF/TARGET/SHAM counterfactuals without inference?", ("d3_counterfactuals.jsonl", "d3_assistance_events.jsonl")),
        ("Q8", "Can assess nondeterminism, cache, order, carryover and runtime effects?", ("d3_reproducibility_calibration.jsonl", "d3_runtime_telemetry.jsonl")),
        ("Q9", "Can distinguish missingness reasons from ambiguous nulls?", ("d3_missingness_summary.json", "d3_capture_completeness.json")),
        ("Q10", "Can derive structural case predictors and normalized model behavior?", ("d3_case_structural_features.jsonl", "d3_model_behavior_features.jsonl")),
        ("Q11", "Can trace supporting and contradictory evidence per causal claim?", ("d3_causal_claim_graph.jsonl", "d3_claim_evidence_edges.jsonl")),
        ("Q12", "Can identify uncovered experiment space and why it is uncovered?", ("d3_coverage_matrix.json", "d3_uncovered_space.jsonl")),
        ("Q13", "Can trace retained architecture components to evidence?", ("d3_causal_claim_graph.jsonl", "d3_component_manifest.jsonl")),
        ("Q14", "Can trace excluded components to harm, futility, redundancy or unresolved evidence?", ("d3_causal_claim_graph.jsonl", "d3_evidence_saturation.jsonl")),
        ("Q15", "Can future deterministic scorers, routers and verifiers reevaluate the run without inference?", ("d3_raw_model_requests.jsonl", "d3_raw_model_responses.jsonl", "d3_scores_raw.jsonl", "d3_data_dictionary.json")),
    )
    rows: list[dict[str, Any]] = []
    for check_id, question, files in questions:
        present = all((root / name).exists() for name in files)
        rows.append(
            {
                "id": check_id,
                "question": question,
                "passed": present,
                "status": "SCHEMA_READY_ZERO_CALL" if model_free else ("AVAILABLE_FOR_EMPIRICAL_AUDIT" if present else "MISSING"),
                "required_artifacts": list(files),
            }
        )
    return rows


def finalize_d3_package(
    root: str | Path,
    *,
    planner: D3ExperimentPlanner,
    config: Mapping[str, Any],
    model_free: bool,
    campaign_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(root)
    output.mkdir(parents=True, exist_ok=True)
    store = D3EvidenceStore(output)

    coverage = _coverage(planner, output)
    capture = _capture_completeness(output)
    missingness = _missingness_summary(output)
    reproducibility = _reproducibility_summary(output, model_free=model_free)
    dictionary = _data_dictionary()

    _write_json(output / "d3_coverage_matrix.json", coverage)
    _write_json(output / "d3_capture_completeness.json", capture)
    _write_json(output / "d3_missingness_summary.json", missingness)
    _write_json(output / "d3_reproducibility_calibration.json", reproducibility)
    _write_json(output / "d3_data_dictionary.json", dictionary)
    _write_json(output / "d3_environment_provenance.json", _environment_provenance(config, model_free=model_free))

    audit_rows = _audit_checks(output, model_free=model_free)
    audit = {
        "schema_version": 1,
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "empirical_claims_authorized": not model_free and capture["physical_model_calls"] > 0,
        "checks": audit_rows,
        "overall_passed": all(row["passed"] for row in audit_rows),
    }
    _write_json(output / "d3_data_value_audit.json", audit)

    result = dict(campaign_result or {})
    report = {
        "schema_version": 1,
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "physical_model_calls": capture["physical_model_calls"],
        "admissible_calls": capture["admissible_calls"],
        "planner_candidates": planner.candidate_count(),
        "audit_passed": audit["overall_passed"],
        "empirical_claims_authorized": audit["empirical_claims_authorized"],
        "campaign_result": result,
    }
    _write_json(output / "d3_final_report.json", report)

    handoff = {
        "schema_version": 1,
        "from_stage": "D3",
        "to_stage": "D4",
        "status": "SCHEMA_READY_ZERO_CALL" if model_free else result.get("final_state", "UNRESOLVED"),
        "physical_model_calls": capture["physical_model_calls"],
        "promotion_authorized": False if model_free else bool(audit["overall_passed"] and result.get("final_state") != "HARD_STOP"),
        "required_inputs": [
            "d3_final_report.json",
            "d3_causal_claim_graph.jsonl",
            "d3_coverage_matrix.json",
            "d3_data_value_audit.json",
        ],
    }
    _write_json(output / "d4_handoff.json", handoff)

    master = {
        "schema_version": 1,
        "campaign": "HARVEST_D_D3_AUTOMATED_TOMOGRAPHY",
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "physical_model_calls": capture["physical_model_calls"],
        "planner_candidates": planner.candidate_count(),
        "audit_passed": audit["overall_passed"],
        "empirical_claims_authorized": audit["empirical_claims_authorized"],
        "files": sorted(path.name for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS.csv"),
    }
    _write_json(output / "00-HARVEST-D-D3-MASTER-INDEX.json", master)

    store.finalize_manifest()
    return master
