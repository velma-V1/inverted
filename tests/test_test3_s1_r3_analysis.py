from __future__ import annotations

import importlib


R3_FAMILIES = (
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
)

R3_ORDERS = {
    "S1-A0": None,
    "S1-A1": "requirement_validator -> retry -> targeted_repair -> final_validator",
    "S1-A2": "requirement_validator -> targeted_repair -> final_validator -> retry",
    "S1-A3": "requirement_validator -> targeted_repair -> retry -> final_validator",
}


def _analysis():
    return importlib.import_module("inverted.test3_s1_r3_analysis")


def _family(index: int) -> str:
    return "repair_containment" if index == 24 else R3_FAMILIES[index % 6]


def _rows(outcomes=None, catastrophes=None, *, orders=None):
    outcomes = outcomes or {}
    catastrophes = catastrophes or {}
    orders = dict(R3_ORDERS if orders is None else orders)
    rows = []
    for index in range(25):
        task_id = f"r3-t{index:02d}"
        defaults = {arm: False for arm in R3_ORDERS}
        defaults.update(outcomes.get(index, {}))
        for arm in R3_ORDERS:
            success = bool(defaults[arm])
            rows.append({
                "protocol_revision": "S1-R3",
                "holdout": "A-R3",
                "task_id": task_id,
                "arm_id": arm,
                "order": orders[arm],
                "family": _family(index),
                "complexity": 4 if index == 24 else (index // 6) + 1,
                "complete": True,
                "seed_failure_verified": True,
                "seed_passed_requirements": ["p1"],
                "seed_failed_requirements": ["f1"],
                "final_passed_requirements": ["p1", "f1"] if success else ["p1"],
                "final_failed_requirements": [] if success else ["f1"],
                "requirement_kinds": {"p1": "preserve", "f1": "equal"},
                "first_active_component": (
                    "best_single_regenerate" if arm == "S1-A0" else
                    "retry" if arm == "S1-A1" else "targeted_repair"
                ),
                "active_inference_calls": 1,
                "shadow_inference_calls": 1,
                "intervention_exposure_valid": True,
                "cache_hits": 0,
                "success": success,
                "catastrophic": bool(catastrophes.get((index, arm), False)),
                "physical_calls_added": 2,
                "total_tokens": 100,
                "latency_s": 1.0,
            })
    return rows


def test_r3_analysis_accepts_exact_25_task_200_call_unique_causal_order_contract():
    analysis = _analysis()
    summary = analysis.summarize_s1_r3(_rows())
    assert summary["protocol_revision"] == "S1-R3"
    assert summary["holdout"] == "A-R3"
    assert summary["detected_protocol_contract"] == "S1-R3"
    assert summary["matched_task_count"] == 25
    assert summary["total_matched_physical_calls"] == 200
    assert summary["protocol_valid_for_primary_claim"] is True
    assert summary["intervention_exposure"]["causal_order_signatures_unique"] is True
    assert len(summary["intervention_exposure"]["causal_order_signatures"]) == 3
    assert {row["family"] for row in summary["family_summaries"]} == set(R3_FAMILIES)


def test_r3_analysis_invalidates_perfect_call_accounting_when_control_causal_order_collapses():
    analysis = _analysis()
    orders = dict(R3_ORDERS)
    orders["S1-A3"] = "retry -> targeted_repair -> final_validator -> requirement_validator"
    summary = analysis.summarize_s1_r3(_rows(orders=orders))
    verdict = analysis.derive_s1_r3_verdict(summary, full_power_clusters=260)
    assert summary["total_matched_physical_calls"] == 200
    assert summary["protocol_valid_for_primary_claim"] is False
    assert "causal_order_signatures_unique" in summary["protocol_failures"]
    assert verdict["verdict"] == "S1_R3_INVALID_PROTOCOL"
    assert verdict["tier_a_architecture_claim"] is False


def test_r3_aggregate_large_signal_uses_same_frozen_5_and_3_thresholds():
    analysis = _analysis()
    outcomes = {
        index: {"S1-A0": False, "S1-A1": True, "S1-A2": False, "S1-A3": False}
        for index in range(5)
    }
    verdict = analysis.derive_s1_r3_verdict(analysis.summarize_s1_r3(_rows(outcomes)), full_power_clusters=260)
    assert verdict["verdict"] == "S1_R3_FIXED_ORDER_LARGE_SIGNAL"
    assert verdict["winning_arm_id"] == "S1-A1"
    assert verdict["net_wins_vs_baseline"] == 5
    assert verdict["net_wins_vs_random_control"] == 5
    assert verdict["tier_a_architecture_claim"] is True


def test_r3_category_signal_uses_same_frozen_family_thresholds():
    analysis = _analysis()
    preservation = [i for i in range(25) if _family(i) == "preservation"][:2]
    containment = [i for i in range(25) if _family(i) == "repair_containment"][:2]
    outcomes = {
        index: {"S1-A0": False, "S1-A1": True, "S1-A2": False, "S1-A3": False}
        for index in preservation + containment
    }
    verdict = analysis.derive_s1_r3_verdict(analysis.summarize_s1_r3(_rows(outcomes)), full_power_clusters=260)
    assert verdict["verdict"] == "S1_R3_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL"
    assert verdict["winning_arm_id"] == "S1-A1"
    assert set(verdict["strong_families"]) == {"preservation", "repair_containment"}
    assert verdict["routing_hypothesis_supported"] is True
    assert verdict["tier_a_architecture_claim"] is False


def test_r3_harmful_and_nondecisive_verdicts_keep_r2_preregistered_boundaries():
    analysis = _analysis()
    harmful_outcomes = {
        index: {"S1-A0": True, "S1-A1": False, "S1-A2": False, "S1-A3": False}
        for index in range(3)
    }
    harmful = analysis.derive_s1_r3_verdict(
        analysis.summarize_s1_r3(_rows(harmful_outcomes)), full_power_clusters=260
    )
    assert harmful["verdict"] == "S1_R3_FIXED_ORDER_NEGATIVE_OR_HARMFUL"
    assert harmful["tier_a_architecture_claim"] is False

    all_pass = {index: {arm: True for arm in R3_ORDERS} for index in range(25)}
    null = analysis.derive_s1_r3_verdict(analysis.summarize_s1_r3(_rows(all_pass)), full_power_clusters=260)
    assert null["verdict"] == "S1_R3_SCREEN_NON_DECISIVE"
    assert null["cannot_rule_out_target_effect"] is True
    assert null["tier_a_architecture_claim"] is False
