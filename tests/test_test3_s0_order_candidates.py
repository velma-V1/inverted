from __future__ import annotations

import json
from pathlib import Path

from inverted.test3_s1_freeze import derive_s1_order_candidates, select_s1_fixed_orders
from inverted.test3_s0_artifacts import Test3S0ArtifactWriter


def _comparisons() -> list[dict[str, str]]:
    return [
        {
            "source_id": "test2-model-free",
            "source_file": "order/order-ranking.csv",
            "record_type": "comparison_csv",
            "rank": "2",
            "order": "validator -> retry -> repair",
            "components": '["validator","retry","repair"]',
            "causal_status": "CAUSAL_REPLAY",
            "simulated_success_rate": "0.81",
            "blocked_rate": "0.02",
            "catastrophic_rate": "0.01",
            "n": "12000",
        },
        {
            "source_id": "test2-model-free",
            "source_file": "order/order-ranking.csv",
            "record_type": "comparison_csv",
            "rank": "1",
            "order": "retry -> validator -> repair",
            "components": '["retry","validator","repair"]',
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "simulated_success_rate": "0.84",
            "blocked_rate": "0.01",
            "catastrophic_rate": "0.00",
            "n": "12000",
        },
        {
            "source_id": "test2-model-free",
            "source_file": "effects/standalone-effects.csv",
            "record_type": "comparison_csv",
            "component": "retry",
            "success_rate": "0.75",
        },
    ]


def _messy_comparisons() -> list[dict[str, str]]:
    return _comparisons() + [
        {
            "source_id": "test2-tier-a",
            "source_file": "order/order-ranking.csv",
            "record_type": "comparison_csv",
            "rank": "1",
            "order": "retry -> validator -> repair",
            "components": '["retry","validator","repair"]',
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "simulated_success_rate": "0.84",
            "blocked_rate": "0.01",
            "catastrophic_rate": "0.00",
            "n": "12000",
        },
        {
            "source_id": "test2-model-free",
            "source_file": "order/order-ranking.csv",
            "record_type": "comparison_csv",
            "rank": "0",
            "order": "oracle_auditor -> retry -> validator -> repair",
            "components": '["oracle_auditor","retry","validator","repair"]',
            "causal_status": "CAUSAL_REPLAY",
            "simulated_success_rate": "1.0",
            "blocked_rate": "0.0",
            "catastrophic_rate": "0.0",
            "n": "12000",
        },
    ]


def test_order_comparison_evidence_recovers_explicit_s1_fixed_policy_candidates():
    rows = derive_s1_order_candidates(_comparisons())
    assert [row["candidate"] for row in rows] == [
        "retry -> validator -> repair",
        "validator -> retry -> repair",
    ]
    assert rows[0]["rank"] == 1
    assert rows[0]["evidence_basis"] == "MODEL_FREE_ORDER_RANKING_HYPOTHESIS"
    assert rows[0]["tier_a_architecture_claim"] is False
    assert rows[0]["causal_status"] == "REQUIRES_NEW_INFERENCE"
    assert rows[0]["verified_success_rate"] is None
    assert rows[0]["simulated_success_rate"] == 0.84
    assert rows[1]["causal_status"] == "CAUSAL_REPLAY"
    assert rows[1]["simulated_success_rate"] == 0.81


def test_order_candidates_deduplicate_sources_and_quarantine_oracle_orders():
    rows = derive_s1_order_candidates(_messy_comparisons())
    assert len(rows) == 3

    duplicate = next(row for row in rows if row["candidate"] == "retry -> validator -> repair")
    assert duplicate["source_count"] == 2
    assert duplicate["source_ids"] == ["test2-model-free", "test2-tier-a"]

    oracle = next(row for row in rows if "oracle_auditor" in row["candidate"])
    assert oracle["production_eligible"] is False
    assert oracle["analysis_only_components"] == ["oracle_auditor"]
    assert "analysis-only" in oracle["exclusion_reason"]

    selected = select_s1_fixed_orders(rows, count=2)
    assert [row["candidate"] for row in selected] == [
        "retry -> validator -> repair",
        "validator -> retry -> repair",
    ]
    assert all("oracle_auditor" not in row["candidate"] for row in selected)


def test_artifact_writer_promotes_order_rankings_and_unblocks_s1_arm_selection(tmp_path: Path):
    packet = tmp_path / "packet"
    Test3S0ArtifactWriter(packet).write_all({
        "comparison_evidence": _comparisons(),
        "candidate_section1_preregistration": {
            "status": "CANDIDATE_ONLY_NOT_PREREGISTERED",
            "tier_a_inference_authorized": False,
            "exact_budget": None,
            "power_evidence": {
                "status": "OK",
                "recommended_clusters": 260,
                "cluster_sd": 0.17260694743980193,
                "target_effect": 0.03,
            },
        },
    })

    prereg = json.loads((packet / "candidate_section1_preregistration.json").read_text(encoding="utf-8"))
    assert prereg["arm_freeze_ready"] is True
    assert prereg["fixed_policy_candidate_count"] == 2
    assert "arm_freeze_blocker" not in prereg

    text = (packet / "fixed_policy_candidates.csv").read_text(encoding="utf-8")
    assert "retry -> validator -> repair" in text
    assert "MODEL_FREE_ORDER_RANKING_HYPOTHESIS" in text


def test_artifact_writer_emits_final_non_oracle_four_arm_s1_screen(tmp_path: Path):
    packet = tmp_path / "packet"
    Test3S0ArtifactWriter(packet).write_all({
        "comparison_evidence": _messy_comparisons(),
        "candidate_section1_preregistration": {
            "status": "CANDIDATE_ONLY_NOT_PREREGISTERED",
            "tier_a_inference_authorized": False,
            "exact_budget": None,
            "power_evidence": {
                "status": "OK",
                "recommended_clusters": 260,
                "cluster_sd": 0.17260694743980193,
                "target_effect": 0.03,
            },
        },
    })

    prereg = json.loads((packet / "candidate_section1_preregistration.json").read_text(encoding="utf-8"))
    assert prereg["arm_freeze_ready"] is True
    assert prereg["production_eligible_fixed_order_count"] == 2
    assert prereg["selected_fixed_orders"] == [
        "retry -> validator -> repair",
        "validator -> retry -> repair",
    ]
    assert prereg["exact_budget"] == 80
    assert prereg["budget_unit"] == "physical_model_calls"
    assert prereg["arm_count"] == 4
    assert prereg["physical_call_cap_per_arm"] == 20
    assert prereg["full_power_cluster_requirement"] == 260
    assert prereg["screen_is_underpowered_for_target_effect"] is True
    assert prereg["tier_a_inference_authorized"] is False

    arms = prereg["arms"]
    assert [arm["role"] for arm in arms] == [
        "best_single_model_baseline",
        "current_best_fixed_hybrid",
        "alternate_fixed_order",
        "random_order_negative_control",
    ]
    assert arms[1]["order"] == "retry -> validator -> repair"
    assert arms[2]["order"] == "validator -> retry -> repair"
    assert all("oracle_auditor" not in str(arm.get("order", "")) for arm in arms)
    assert "oracle_auditor" not in arms[3]["order"]
