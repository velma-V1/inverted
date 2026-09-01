from inverted.models import MockModelAdapter
from inverted.test3_s2_analysis import derive_s2_verdict, summarize_s2
from inverted.test3_s2_cases import build_holdout_b
from inverted.test3_s2_runtime import run_s2_screen


def _models():
    return {
        "qwen3.5:9b-q8_0": MockModelAdapter("qwen3.5:9b-q8_0"),
        "cogito:3b-v1-preview-llama-q8_0": MockModelAdapter("cogito:3b-v1-preview-llama-q8_0"),
        "llama3.1:8b": MockModelAdapter("llama3.1:8b"),
    }


def test_s2_summary_contains_all_primary_estimands_and_observed_oracle():
    runtime = run_s2_screen(cases=build_holdout_b(), model_by_name=_models(), run_id="analysis-mock")
    summary = summarize_s2(runtime)
    assert summary["protocol_valid_for_primary_claim"] is True
    assert len(summary["arm_summaries"]) == 5
    assert len(summary["family_summaries"]) == 30
    assert len(summary["perturbation_summaries"]) == 15
    assert len(summary["complexity_summaries"]) == 20
    assert len(summary["pairwise_effects"]) >= 5
    assert len(summary["action_transition_matrix"]) > 0
    assert len(summary["regret_to_oracle"]) == 5
    assert summary["observed_oracle"]["matched_cases"] == 72
    assert summary["observed_oracle"]["successes"] == 72


def test_s2_signal_requires_b3_to_beat_fixed_random_and_survive_divergence_exclusion():
    summary = {
        "protocol_valid_for_primary_claim": True,
        "protocol_failures": [],
        "pairwise_index": {
            "S2-B3|S2-B0": {"net_wins": 6, "success_rate_delta": 0.083, "catastrophes_added": 0},
            "S2-B3|S2-B4": {"net_wins": 5, "success_rate_delta": 0.070, "catastrophes_added": 0},
            "S2-B2|S2-B1": {"net_wins": 3, "success_rate_delta": 0.042, "catastrophes_added": 0},
        },
        "supported_strata_b3_vs_b0": ["family:state", "family:policy", "perturbation:structural"],
        "regret_index": {"S2-B0": 0.12, "S2-B3": 0.04},
        "divergence_excluded_b3_vs_b0": {"net_wins": 5, "success_rate_delta": 0.071, "catastrophes_added": 0},
        "divergence_excluded_b3_vs_b4": {"net_wins": 4, "success_rate_delta": 0.057, "catastrophes_added": 0},
        "matched_case_count": 72,
    }
    verdict = derive_s2_verdict(summary)
    assert verdict["verdict"] == "S2_ADAPTIVE_ROUTING_SIGNAL"
    assert verdict["failure_evidence_incremental_signal"] is True
    assert verdict["winning_arm_id"] == "S2-B3"


def test_s2_harmful_and_protocol_invalid_have_precedence():
    harmful = {
        "protocol_valid_for_primary_claim": True,
        "protocol_failures": [],
        "pairwise_index": {
            "S2-B3|S2-B0": {"net_wins": -4, "success_rate_delta": -0.06, "catastrophes_added": 0},
            "S2-B3|S2-B4": {"net_wins": 0, "success_rate_delta": 0.0, "catastrophes_added": 0},
            "S2-B2|S2-B1": {"net_wins": 0, "success_rate_delta": 0.0, "catastrophes_added": 0},
        },
        "supported_strata_b3_vs_b0": [],
        "regret_index": {"S2-B0": 0.1, "S2-B3": 0.2},
        "divergence_excluded_b3_vs_b0": {"net_wins": -4, "success_rate_delta": -0.06, "catastrophes_added": 0},
        "divergence_excluded_b3_vs_b4": {"net_wins": 0, "success_rate_delta": 0.0, "catastrophes_added": 0},
        "matched_case_count": 72,
    }
    assert derive_s2_verdict(harmful)["verdict"] == "S2_ADAPTIVE_ROUTING_HARMFUL"

    invalid = dict(harmful)
    invalid["protocol_valid_for_primary_claim"] = False
    invalid["protocol_failures"] = ["exact_720_calls"]
    assert derive_s2_verdict(invalid)["verdict"] == "S2_INVALID_PROTOCOL"
