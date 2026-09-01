from collections import Counter

from inverted.assistant_value.authority import (
    TOOL_CLASSES,
    authority_prompt_payload,
    generate_authority_cases,
    planned_authority_calls,
    policy_proposal,
)


def test_authority_default_plan_is_1080_calls_for_three_models():
    assert planned_authority_calls(3) == 1080


def test_authority_generation_balances_tool_classes_and_is_deterministic():
    cases = generate_authority_cases(seed=20260901, cases_per_class=15)
    assert cases == generate_authority_cases(seed=20260901, cases_per_class=15)
    counts = Counter(case["tool_class"] for case in cases)
    assert counts == Counter({name: 15 for name in TOOL_CLASSES})


def test_policy_proposal_matches_oracle_without_fault_injection():
    cases = generate_authority_cases(seed=11, cases_per_class=4)
    for case in cases:
        proposal = policy_proposal(case, inject_fault=False)
        assert proposal["disposition"] == case["oracle"]["disposition"]
        assert proposal.get("action_id") == case["oracle"].get("action_id")


def test_authority_prompt_contains_public_permissions_but_not_hidden_oracle():
    case = generate_authority_cases(seed=12, cases_per_class=1)[0]
    payload = authority_prompt_payload(case, arm="DIRECT")
    text = repr(payload)
    assert "authorization" in text
    assert "oracle" not in text
    assert "damage_score" not in text
