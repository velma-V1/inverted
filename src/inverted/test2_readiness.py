from __future__ import annotations

from copy import deepcopy
from typing import Any

from .test2_integrity import harden_evidence_integrity
from .test2_metadata import enrich_test2_evidence
from .test2_preregistration import PREREGISTRATION, evaluate_primary_verdict


def _material_contamination_blockers(evidence: dict[str, Any]) -> list[str]:
    diagnostics = evidence.get("diagnostics") or {}
    audit = diagnostics.get("contamination_audit") or {}
    blockers: list[str] = []
    if audit.get("forbidden_prompt_marker_hits"):
        blockers.append("hidden_label_marker_in_prompt")
    if audit.get("duplicate_evaluation_model_rows"):
        blockers.append("duplicate_evaluation_model_rows")
    if audit.get("unique_model_call_identity") is False:
        blockers.append("non_unique_physical_model_call_identity")
    if audit.get("cache_identity_reference_integrity") is False:
        blockers.append("cache_identity_reference_integrity")
    if audit.get("physical_call_number_integrity") is False:
        blockers.append("physical_call_number_integrity")
    if audit.get("physical_call_count_matches_master") is False:
        blockers.append("physical_call_count_mismatch")
    if audit.get("repair_screen_primary_overlap"):
        blockers.append("repair_screen_primary_overlap")
    if audit.get("repair_screen_condition_balance_ok") is False:
        blockers.append("repair_screen_condition_imbalance")
    for key in (
        "orphan_prompt_call_ids",
        "orphan_response_call_ids",
        "missing_prompt_for_call_ids",
        "missing_response_for_call_ids",
    ):
        if audit.get(key):
            blockers.append(key)

    model_provenance = ((evidence.get("provenance") or {}).get("models") or {})
    identity_match = model_provenance.get("identity_match")
    if identity_match is False:
        blockers.append("ollama_identity_drift")
    elif identity_match is not True:
        blockers.append("ollama_identity_snapshot_missing")
    return blockers


def finalize_test2_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Finalize a Test-2 packet using only already-collected evidence.

    This is deliberately post-inference: it may derive diagnostics and verdicts,
    but it never calls a model or external service and therefore cannot alter
    the frozen Tier-A campaign. Decisive local verdicts pass two independent
    metadata/integrity derivations before the preregistered statistics run.
    """
    enrich_test2_evidence(evidence)
    harden_evidence_integrity(evidence)
    evidence["preregistration"] = deepcopy(PREREGISTRATION)
    mode = str((evidence.get("master_index") or {}).get("mode") or "unknown")

    if mode != "local":
        evidence["verdict"] = {
            "verdict": "NON-DECISIVE",
            "evidence_tier": mode,
            "reason": "INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE",
        }
        return evidence

    repair_rows = [
        row for row in (evidence.get("raw") or {}).get("trials", [])
        if row.get("phase") == "repair_factorial"
    ]
    primary = evaluate_primary_verdict(repair_rows)
    blockers = _material_contamination_blockers(evidence)

    if primary.get("verdict") == "NON-DECISIVE":
        evidence["verdict"] = {
            **primary,
            "verdict": "INCONCLUSIVE",
            "reason": "Decisive Tier-A run lacks the complete preregistered matched factorial/physical-call contract.",
            "material_contamination_blockers": blockers,
        }
    elif blockers:
        evidence["verdict"] = {
            "verdict": "INCONCLUSIVE",
            "reason": "Material evidence-integrity contamination prevents a decisive Tier-A interpretation.",
            "material_contamination_blockers": blockers,
            "primary_statistical_verdict": primary,
        }
    else:
        evidence["verdict"] = {**primary, "material_contamination_blockers": []}
    return evidence
