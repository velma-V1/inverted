from __future__ import annotations

from copy import deepcopy
from typing import Any

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
        blockers.append("non_unique_model_call_identity")
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
    the frozen Tier-A campaign.
    """
    enrich_test2_evidence(evidence)
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
            "reason": "Decisive Tier-A run lacks the complete preregistered matched factorial contract.",
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
