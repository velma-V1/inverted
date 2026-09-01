from collections import Counter

from inverted.models import MockModelAdapter
from inverted.test3_s2_cases import build_holdout_b
from inverted.test3_s2_policy import REAL_ARM_IDS
from inverted.test3_s2_runtime import S2_EXACT_BUDGET, S2_TRIAL_COUNT, run_s2_screen


def _models():
    return {
        "qwen3.5:9b-q8_0": MockModelAdapter("qwen3.5:9b-q8_0"),
        "cogito:3b-v1-preview-llama-q8_0": MockModelAdapter("cogito:3b-v1-preview-llama-q8_0"),
        "llama3.1:8b": MockModelAdapter("llama3.1:8b"),
    }


def test_s2_mock_runtime_is_exact_720_equal_compute_and_complete():
    result = run_s2_screen(cases=build_holdout_b(), model_by_name=_models(), run_id="s2-mock")
    assert S2_EXACT_BUDGET == 720
    assert S2_TRIAL_COUNT == 360
    assert result["physical_model_calls"] == 720
    assert result["action_budget"]["combined_used"] == 720
    assert result["action_budget"]["by_kind"] == {"model_call": 720}
    assert len(result["trials"]) == 360
    assert len(result["model_calls"]) == 720
    assert all(row["complete"] is True for row in result["trials"])
    assert all(row["calls_used"] == 2 for row in result["trials"])

    counts = Counter(row["arm_id"] for row in result["model_calls"])
    assert counts == {arm_id: 144 for arm_id in REAL_ARM_IDS}
    trial_counts = Counter(row["arm_id"] for row in result["trials"])
    assert trial_counts == {arm_id: 72 for arm_id in REAL_ARM_IDS}
    assert all(row["cache_hit"] is False for row in result["model_calls"])


def test_s2_runtime_records_routes_revalidation_shadow_and_balanced_positions():
    result = run_s2_screen(cases=build_holdout_b(), model_by_name=_models(), run_id="s2-routing")
    assert len(result["routing_decisions"]) == 720
    assert all(row["action_selected"] in {"retry_qwen", "repair_cogito", "switch_llama"} for row in result["routing_decisions"])
    assert all("evidence_state" in row for row in result["routing_decisions"])
    assert any(row["shadow_only"] for row in result["model_calls"])
    assert len(result["validator_results"]) >= 360
    positions = Counter((row["arm_id"], row["execution_position"]) for row in result["trials"])
    assert all(value in {14, 15} for value in positions.values())


def test_rich_router_second_decision_uses_post_first_call_verified_state():
    result = run_s2_screen(cases=build_holdout_b(), model_by_name=_models(), run_id="s2-state")
    rows = [row for row in result["routing_decisions"] if row["arm_id"] == "S2-B3" and row["step_index"] == 1]
    assert len(rows) == 72
    assert all(row["evidence_state"].get("previous_action") for row in rows)
    assert all(row["evidence_state"].get("previous_model") for row in rows)
