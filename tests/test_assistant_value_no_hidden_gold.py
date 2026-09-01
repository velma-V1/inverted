from copy import deepcopy

from inverted.assistant_value.authority import (
    authority_prompt_payload,
    generate_authority_cases,
    policy_proposal,
)
from inverted.assistant_value.evidence_trust import (
    evidence_prompt_payload,
    generate_evidence_cases,
    resolve_evidence,
)


def test_evidence_public_payload_excludes_oracle_annotation_fields():
    case = generate_evidence_cases(seed=20260901, cases_per_regime=2)[-1]
    payload = evidence_prompt_payload(case, arm="DIRECT")
    text = repr(payload)
    for forbidden in (
        "relevant",
        "supports_action",
        "embedded_instruction",
        "forged_authority",
        "oracle",
        "attacker_target",
    ):
        assert forbidden not in text


def test_evidence_system_resolver_is_invariant_to_hidden_scoring_annotations():
    cases = generate_evidence_cases(seed=44, cases_per_regime=2)
    for case in cases:
        expected = resolve_evidence(case)
        tampered = deepcopy(case)
        for item in tampered["evidence"]:
            item["relevant"] = not bool(item.get("relevant"))
            item["fresh"] = not bool(item.get("fresh"))
            item["supports_action"] = (
                tampered["actions"][0]
                if item.get("supports_action") != tampered["actions"][0]
                else tampered["actions"][-1]
            )
            item["embedded_instruction"] = not bool(item.get("embedded_instruction"))
            item["forged_authority"] = not bool(item.get("forged_authority"))
        assert resolve_evidence(tampered) == expected


def test_authority_public_payload_excludes_precomputed_answer_labels():
    cases = generate_authority_cases(seed=20260901, cases_per_class=12)
    for case in cases:
        payload = authority_prompt_payload(case, arm="DIRECT")
        text = repr(payload)
        for forbidden in (
            "ambiguous",
            "chained_action_risk",
            "request_matches_available_action",
            "oracle",
            "damage_score",
            "scenario",
        ):
            assert forbidden not in text


def test_authority_policy_is_invariant_to_hidden_scoring_annotations():
    cases = generate_authority_cases(seed=91, cases_per_class=12)
    for case in cases:
        expected = policy_proposal(case, inject_fault=False)
        tampered = deepcopy(case)
        if "ambiguous" in tampered["authorization"]:
            tampered["authorization"]["ambiguous"] = not bool(tampered["authorization"]["ambiguous"])
        if "chained_action_risk" in tampered["risk_context"]:
            tampered["risk_context"]["chained_action_risk"] = not bool(tampered["risk_context"]["chained_action_risk"])
        if "request_matches_available_action" in tampered["user_request"]:
            tampered["user_request"]["request_matches_available_action"] = not bool(
                tampered["user_request"]["request_matches_available_action"]
            )
        assert policy_proposal(tampered, inject_fault=False) == expected
