from collections import Counter

from inverted.assistant_value.evidence_trust import (
    EVIDENCE_REGIMES,
    evidence_prompt_payload,
    generate_evidence_cases,
    planned_evidence_calls,
    resolve_evidence,
)


def test_evidence_default_plan_hits_1080_call_ceiling_for_three_models():
    assert planned_evidence_calls(3) == 1080


def test_evidence_generation_balances_regimes_and_is_deterministic():
    cases = generate_evidence_cases(seed=20260901, cases_per_regime=20)
    assert cases == generate_evidence_cases(seed=20260901, cases_per_regime=20)
    counts = Counter(case["regime"] for case in cases)
    assert counts == Counter({name: 20 for name in EVIDENCE_REGIMES})


def test_deterministic_resolver_matches_preregistered_oracle():
    cases = generate_evidence_cases(seed=9, cases_per_regime=5)
    for case in cases:
        result = resolve_evidence(case)
        assert result["disposition"] == case["oracle"]["disposition"]
        assert result.get("action_id") == case["oracle"].get("action_id")


def test_adversarial_cases_contain_inert_untrusted_instructions_but_prompt_hides_gold():
    adversarial = [
        case for case in generate_evidence_cases(seed=3, cases_per_regime=3)
        if case["regime"] == "adversarial"
    ]
    assert adversarial
    assert all(any(item["embedded_instruction"] for item in case["evidence"]) for case in adversarial)

    payload = evidence_prompt_payload(adversarial[0], arm="DIRECT")
    text = repr(payload)
    assert "oracle" not in text
    assert "attacker_target" not in text
