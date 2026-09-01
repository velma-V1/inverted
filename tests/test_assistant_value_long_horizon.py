from inverted.assistant_value.long_horizon import (
    CHALLENGE_TYPES,
    generate_long_horizon_cases,
    long_horizon_prompt_payload,
    planned_long_horizon_calls,
)


def test_long_horizon_default_plan_is_972_calls_for_three_models():
    assert planned_long_horizon_calls(3) == 972


def test_long_horizon_generation_is_deterministic_and_covers_challenges():
    a = generate_long_horizon_cases(seed=20260901, per_horizon=20, horizons=(8, 16, 30))
    b = generate_long_horizon_cases(seed=20260901, per_horizon=20, horizons=(8, 16, 30))
    assert a == b
    assert {case["horizon"] for case in a} == {8, 16, 30}

    observed = {
        step["challenge"]
        for case in a
        for step in case["steps"]
        if step["challenge"] is not None
    }
    assert set(CHALLENGE_TYPES).issubset(observed)

    for case in a:
        assert len(case["steps"]) == case["horizon"]
        for step in case["steps"]:
            action_ids = {item["action_id"] for item in step["public"]["actions"]}
            assert step["oracle"]["action_id"] in action_ids


def test_long_horizon_prompt_never_contains_hidden_oracle_fields():
    case = generate_long_horizon_cases(seed=17, per_horizon=1, horizons=(8,))[0]
    payload = long_horizon_prompt_payload(
        case,
        step_index=0,
        state={"completed": [], "values": {}, "protected": {"intact": True}},
        arm="DIRECT",
    )
    text = repr(payload)
    assert "oracle" not in text
    assert case["steps"][0]["oracle"]["action_id"] not in text or any(
        option["action_id"] == case["steps"][0]["oracle"]["action_id"]
        for option in payload["actions"]
    )
