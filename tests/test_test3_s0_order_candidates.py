from __future__ import annotations

import json
from pathlib import Path

from inverted.test3_s0_analysis import derive_fixed_policy_candidates_from_comparisons
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


def test_order_comparison_evidence_recovers_explicit_s1_fixed_policy_candidates():
    rows = derive_fixed_policy_candidates_from_comparisons(_comparisons())
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


def test_artifact_writer_promotes_order_rankings_and_unblocks_s1_arm_selection(tmp_path: Path):
    packet = tmp_path / "packet"
    Test3S0ArtifactWriter(packet).write_all({
        "comparison_evidence": _comparisons(),
        "candidate_section1_preregistration": {
            "status": "CANDIDATE_ONLY_NOT_PREREGISTERED",
            "tier_a_inference_authorized": False,
            "exact_budget": None,
        },
    })

    prereg = json.loads((packet / "candidate_section1_preregistration.json").read_text(encoding="utf-8"))
    assert prereg["arm_freeze_ready"] is True
    assert prereg["fixed_policy_candidate_count"] == 2
    assert "arm_freeze_blocker" not in prereg

    text = (packet / "fixed_policy_candidates.csv").read_text(encoding="utf-8")
    assert "retry -> validator -> repair" in text
    assert "MODEL_FREE_ORDER_RANKING_HYPOTHESIS" in text
