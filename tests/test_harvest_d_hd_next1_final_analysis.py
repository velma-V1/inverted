from __future__ import annotations

from inverted.harvest_d.hd_next1_final_analysis import analyze_protected_evidence


def _rows(retained_components=("I4",)):
    rows = []
    for i in range(63):
        partition = "hd-next1-fresh" if i < 32 else "hd-next1-sealed"
        case_id = f"p-{i:03d}"
        common = {"case_id": case_id, "partition": partition, "stage": "T6_FRESH_CONFIRMATION" if i < 32 else "T6_SEALED_CONFIRMATION"}
        rows.append({**common, "model_key": "SMALL_A", "treatment_role": "CONFIRM_PROMOTED_POLICY", "verified_outcome_correct": True})
        rows.append({**common, "model_key": "QWEN", "treatment_role": "CONFIRM_PROMOTED_POLICY", "verified_outcome_correct": True})
        rows.append({**common, "model_key": "SMALL_A", "treatment_role": "CONFIRM_STRONGEST_CHALLENGER", "verified_outcome_correct": i >= 10})
        rows.append({**common, "model_key": "SMALL_A", "treatment_role": "CONFIRM_RAW_BASELINE", "verified_outcome_correct": i >= 15})
        rows.append({**common, "model_key": "SMALL_A", "treatment_role": "CONFIRM_NEGATIVE_TRANSFER_CONTROL", "verified_outcome_correct": i >= 12})
    freeze = {
        "retained_components": list(retained_components),
        "strongest_ablation_component": retained_components[0] if retained_components else None,
        "candidate_boundary": None,
    }
    return rows, freeze


def test_final_analysis_closes_all_three_questions_only_to_supported_strength():
    rows, freeze = _rows(("I4",))
    report = analyze_protected_evidence(rows, freeze)
    assert report["Q-MODEL-SUBSTITUTION"]["action"] == "SMALL_A_OWNS"
    assert report["Q-MINIMUM-SUPPORT"]["claim"] == "MINIMUM_SUFFICIENT"
    assert report["Q-NEGATIVE-TRANSFER-BOUNDARY"]["state"] == "HARMFUL"
    assert report["Q-NEGATIVE-TRANSFER-BOUNDARY"]["router_promoted"] is False


def test_multiple_unconfirmed_retained_components_downgrade_minimum_claim():
    rows, freeze = _rows(("I4", "A3"))
    report = analyze_protected_evidence(rows, freeze)
    assert report["Q-MINIMUM-SUPPORT"]["claim"] == "SMALLEST_DEFENSIBLE_TESTED_PACKET"
