from __future__ import annotations

import csv
import json
from pathlib import Path

from inverted.test3_s1_freeze import derive_s1_order_candidates, select_s1_fixed_orders
from inverted.test3_s0_artifacts import Test3S0ArtifactWriter


def _production_row(*, rank: str, order: str, rate: str, source_id: str = "test2-model-free") -> dict[str, str]:
    components = [part.strip() for part in order.split("->")]
    return {
        "source_id": source_id,
        "source_file": "order/order-ranking-production.csv",
        "record_type": "comparison_csv",
        "rank": rank,
        "order": order,
        "components": json.dumps(components),
        "causal_status": "REQUIRES_NEW_INFERENCE" if "repair" in order else "CAUSAL_REPLAY",
        "changes_upstream_prompt": "True" if "repair" in order else "False",
        "simulated_success_rate": rate,
        "blocked_rate": "0.01",
        "catastrophic_rate": "0.00",
        "n": "12000",
        "production_eligible": "True",
        "evidence_scope": "PRODUCTION_ORDER_HYPOTHESIS",
    }


def _comparisons() -> list[dict[str, str]]:
    return [
        _production_row(rank="2", order="validator -> retry -> repair -> final_validator", rate="0.81"),
        _production_row(rank="1", order="retry -> validator -> repair -> final_validator", rate="0.84"),
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
        _production_row(
            rank="1",
            order="retry -> validator -> repair -> final_validator",
            rate="0.84",
            source_id="test2-tier-a",
        ),
        {
            "source_id": "test2-model-free",
            "source_file": "order/order-ranking.csv",
            "record_type": "comparison_csv",
            "rank": "1",
            "order": "oracle_auditor -> retry -> validator -> repair -> final_validator",
            "components": '["oracle_auditor","retry","validator","repair","final_validator"]',
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "simulated_success_rate": "1.0",
            "blocked_rate": "0.0",
            "catastrophic_rate": "0.0",
            "n": "12000",
        },
    ]


def test_order_comparison_evidence_recovers_only_explicit_production_s1_candidates():
    rows = derive_s1_order_candidates(_messy_comparisons())
    assert [row["candidate"] for row in rows] == [
        "retry -> validator -> repair -> final_validator",
        "validator -> retry -> repair -> final_validator",
    ]
    assert all("oracle_auditor" not in row["candidate"] for row in rows)
    assert all(row["production_eligible"] is True for row in rows)
    assert all(row["evidence_basis"] == "MODEL_FREE_PRODUCTION_ORDER_RANKING_HYPOTHESIS" for row in rows)
    assert rows[0]["tier_a_architecture_claim"] is False
    assert rows[0]["verified_success_rate"] is None
    assert rows[0]["simulated_success_rate"] == 0.84


def test_order_candidates_deduplicate_production_sources_and_ignore_oracle_ceiling_ranking():
    rows = derive_s1_order_candidates(_messy_comparisons())
    assert len(rows) == 2
    duplicate = next(row for row in rows if row["candidate"].startswith("retry ->"))
    assert duplicate["source_count"] == 2
    assert duplicate["source_ids"] == ["test2-model-free", "test2-tier-a"]
    selected = select_s1_fixed_orders(rows, count=2)
    assert [row["candidate"] for row in selected] == [
        "retry -> validator -> repair -> final_validator",
        "validator -> retry -> repair -> final_validator",
    ]


def test_artifact_writer_promotes_production_order_rankings_and_records_oracle_source_boundary(tmp_path: Path):
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
    assert prereg["fixed_policy_candidate_count"] == 2
    assert prereg["production_eligible_fixed_order_count"] == 2
    assert prereg["selected_fixed_orders"] == [
        "retry -> validator -> repair -> final_validator",
        "validator -> retry -> repair -> final_validator",
    ]
    assert prereg["exact_budget"] == 80
    assert prereg["budget_unit"] == "physical_model_calls"
    assert prereg["arm_count"] == 4
    assert prereg["physical_call_cap_per_arm"] == 20
    assert prereg["full_power_cluster_requirement"] == 260
    assert prereg["screen_is_underpowered_for_target_effect"] is True
    assert prereg["tier_a_inference_authorized"] is False
    assert all("oracle_auditor" not in str(arm.get("order", "")) for arm in prereg["arms"])

    fixed = list(csv.DictReader((packet / "fixed_policy_candidates.csv").open(encoding="utf-8", newline="")))
    assert fixed
    assert all("oracle_auditor" not in row["candidate"] for row in fixed)

    edges = list(csv.DictReader((packet / "edge_cases.csv").open(encoding="utf-8", newline="")))
    boundary = [row for row in edges if row.get("classification") == "oracle_inclusive_order_atlas_not_production_candidate_source"]
    assert boundary
    assert int(boundary[0]["source_row_count"]) == 1


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
    arms = prereg["arms"]
    assert [arm["role"] for arm in arms] == [
        "best_single_model_baseline",
        "current_best_fixed_hybrid",
        "alternate_fixed_order",
        "random_order_negative_control",
    ]
    assert arms[1]["order"] == "retry -> validator -> repair -> final_validator"
    assert arms[2]["order"] == "validator -> retry -> repair -> final_validator"
    assert all("oracle_auditor" not in str(arm.get("order", "")) for arm in arms)
    assert "oracle_auditor" not in arms[3]["order"]
