from inverted.test3_s2_policy import INTERVENTION_LIBRARY, public_router_state, select_action


def _state():
    return {
        "family": "dependency_order",
        "complexity": 3,
        "failed_requirement_ids": ["r7"],
        "failed_requirement_kinds": ["action_before"],
        "failed_count": 1,
        "failure_signature": "action_before:grant>start",
        "deterministic_success": False,
        "catastrophic": False,
        "previous_action": "retry_qwen",
        "previous_model": "qwen3.5:9b-q8_0",
        "retry_count": 1,
        "budget_spent": 1,
        "budget_remaining": 719,
        "perturbation_class": "structural",
        "target_state": {"secret": True},
    }


def test_all_real_arms_share_identical_intervention_library():
    assert INTERVENTION_LIBRARY == ("retry_qwen", "repair_cogito", "switch_llama")


def test_router_feature_boundaries_remove_forbidden_and_arm_specific_features():
    raw = _state()
    b1 = public_router_state("S2-B1", raw)
    b2 = public_router_state("S2-B2", raw)
    b3 = public_router_state("S2-B3", raw)

    assert set(b1) == {"family"}
    assert "family" not in b2 and "complexity" not in b2
    assert {"failed_requirement_kinds", "failed_count", "failure_signature"}.issubset(b2)
    assert {"family", "complexity", "failure_signature", "previous_action", "budget_remaining"}.issubset(b3)
    for view in (b1, b2, b3):
        assert "perturbation_class" not in view
        assert "target_state" not in view


def test_seeded_random_router_is_deterministic_and_all_actions_are_valid():
    raw = _state()
    first = [select_action("S2-B4", raw, step_index=i, random_seed=41001) for i in (0, 1)]
    second = [select_action("S2-B4", raw, step_index=i, random_seed=41001) for i in (0, 1)]
    assert first == second
    assert all(action in INTERVENTION_LIBRARY for action in first)


def test_fixed_control_is_retry_then_repair():
    raw = _state()
    assert select_action("S2-B0", raw, step_index=0, random_seed=0) == "retry_qwen"
    assert select_action("S2-B0", raw, step_index=1, random_seed=0) == "repair_cogito"
