from __future__ import annotations

from inverted.test2_preregistration import PREREGISTRATION, evaluate_primary_verdict


def _repair_rows(st_successes: int, rr_successes: int, n: int = 18, st_catastrophic: int = 0, rr_catastrophic: int = 0):
    rows = []
    for i in range(n):
        model = f"m{i % 3}"
        task = f"t{i}"
        rows.append({
            "model": model, "task_id": task, "feedback_style": "structured", "strategy": "targeted",
            "success": i < st_successes, "catastrophic": i < st_catastrophic,
        })
        rows.append({
            "model": model, "task_id": task, "feedback_style": "raw", "strategy": "regenerate",
            "success": i < rr_successes, "catastrophic": i < rr_catastrophic,
        })
    return rows


def test_preregistration_declares_tier_a_budget_gates_and_evidence_contract():
    assert PREREGISTRATION["evidence_tier"] == "A"
    assert PREREGISTRATION["hard_physical_call_ceiling"] == 480
    assert PREREGISTRATION["stopping_rule"] == "FIXED_BUDGET_NO_SEQUENTIAL_EARLY_STOP"
    assert PREREGISTRATION["primary_hypothesis"]["minimum_effect_pp"] == 10.0
    assert PREREGISTRATION["primary_hypothesis"]["third_retry_break_even"] == 0.3431
    assert PREREGISTRATION["failure_gates"]["catastrophic_increase_pp"] == 2.0
    required = set(PREREGISTRATION["evidence_contract"])
    assert {"events.jsonl", "model_calls.jsonl", "trials.csv", "trials.jsonl", "failures.csv", "summary.json", "summary.csv", "report.txt", "config.json", "provenance.json", "SHA256SUMS.csv", "TEST2-NEXT-STRIDE-REPORT.txt"} <= required


def test_supported_requires_all_success_gates_and_confidence():
    result = evaluate_primary_verdict(_repair_rows(st_successes=17, rr_successes=6))
    assert result["verdict"] == "SUPPORTED"
    assert result["structured_targeted"]["ci95_low"] > 0.3431
    assert result["paired_effect_pp"] >= 10.0
    assert result["paired_effect_ci95_low_pp"] > 0.0
    assert result["catastrophic_delta_pp"] < 2.0


def test_refuted_on_catastrophic_gate_even_if_success_rises():
    result = evaluate_primary_verdict(_repair_rows(st_successes=17, rr_successes=6, st_catastrophic=2))
    assert result["verdict"] == "REFUTED"
    assert "catastrophic" in " ".join(result["failure_reasons"]).lower()


def test_refuted_when_repair_cannot_beat_third_retry_break_even_with_95pct_confidence():
    result = evaluate_primary_verdict(_repair_rows(st_successes=2, rr_successes=2))
    assert result["verdict"] == "REFUTED"
    assert result["structured_targeted"]["ci95_high"] <= 0.3431


def test_inconclusive_when_direction_is_promising_but_confidence_gates_are_not_met():
    result = evaluate_primary_verdict(_repair_rows(st_successes=10, rr_successes=8))
    assert result["verdict"] == "INCONCLUSIVE"


def test_non_decisive_when_required_factorial_cells_are_incomplete():
    rows = _repair_rows(st_successes=17, rr_successes=6)
    rows.pop()
    result = evaluate_primary_verdict(rows)
    assert result["verdict"] == "NON-DECISIVE"
