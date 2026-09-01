from copy import deepcopy

from inverted.assistant_value import TEST_CALL_CAPS, TEST_NAMES
from inverted.assistant_value.ground_truth_isolation import (
    LEAK_REGIMES,
    derive_probe_candidate,
    detect_artifact_leak,
    generate_ground_truth_cases,
    ground_truth_prompt_payload,
    inject_ground_truth_leak,
    planned_ground_truth_calls,
)


def test_ground_truth_isolation_is_registered_with_exact_1080_call_default():
    assert "ground_truth_isolation" in TEST_NAMES
    assert TEST_CALL_CAPS["ground_truth_isolation"] == 1080
    assert len(LEAK_REGIMES) == 12
    assert planned_ground_truth_calls(3, 10, len(LEAK_REGIMES), 3) == 1080


def test_clean_prompt_and_probe_candidate_are_hidden_truth_invariant():
    case = generate_ground_truth_cases(seed=20260901, cases_per_regime=1)[0]
    candidate = derive_probe_candidate(case)
    payload = ground_truth_prompt_payload(case, arm="INVERTED", candidate=candidate)

    tampered = deepcopy(case)
    tampered["oracle"]["correct_action_id"] = "not-a-real-action"
    tampered["oracle"]["secret_bit"] = 999
    tampered["oracle"]["canary"] = "TOTALLY-DIFFERENT-HIDDEN-CANARY"

    assert derive_probe_candidate(tampered) == candidate
    assert ground_truth_prompt_payload(tampered, arm="INVERTED", candidate=candidate) == payload


def test_detector_has_zero_false_positive_on_clean_control_and_catches_key_leaks():
    cases = generate_ground_truth_cases(seed=9, cases_per_regime=1)
    by_regime = {case["regime"]: case for case in cases}

    clean_case = by_regime["clean_control"]
    clean_payload = ground_truth_prompt_payload(clean_case, arm="DIRECT")
    clean_control = {"route_bucket": "neutral", "cache": {}}
    clean_detection = detect_artifact_leak(
        baseline={"payload": clean_payload, "control": clean_control},
        observed={"payload": clean_payload, "control": clean_control},
        canaries=[clean_case["oracle"]["canary"]],
    )
    assert clean_detection["ensemble_detected"] is False

    for regime in ("direct_oracle", "canary_reversed", "canary_base64", "shared_state_cache"):
        case = by_regime[regime]
        baseline_payload = ground_truth_prompt_payload(case, arm="DIRECT")
        baseline_control = {"route_bucket": "neutral", "cache": {}}
        observed_payload, observed_control, _ = inject_ground_truth_leak(
            case,
            payload=baseline_payload,
            control=baseline_control,
        )
        detection = detect_artifact_leak(
            baseline={"payload": baseline_payload, "control": baseline_control},
            observed={"payload": observed_payload, "control": observed_control},
            canaries=[case["oracle"]["canary"]],
        )
        assert detection["ensemble_detected"] is True, regime


def test_each_planted_regime_changes_only_test_harness_artifacts_not_clean_builder():
    cases = generate_ground_truth_cases(seed=111, cases_per_regime=1)
    for case in cases:
        baseline = ground_truth_prompt_payload(case, arm="CHECKED")
        before = deepcopy(baseline)
        control = {"route_bucket": "neutral", "cache": {}}
        observed_payload, observed_control, injection = inject_ground_truth_leak(
            case,
            payload=baseline,
            control=control,
        )
        assert baseline == before
        assert injection["regime"] == case["regime"]
        if case["regime"] == "clean_control":
            assert observed_payload == baseline
            assert observed_control == control
            assert injection["planted"] is False
        else:
            assert injection["planted"] is True
            assert observed_payload != baseline or observed_control != control
