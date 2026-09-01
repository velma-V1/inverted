from inverted.test3_s2_runtime import detect_stochastic_divergence


def test_same_prompt_fingerprint_different_response_is_first_class_evidence():
    rows = [
        {
            "arm_id": "S2-B2", "task_id": "t1", "call_identity": "same",
            "prompt_fingerprint": "same", "response_digest": "aaa", "response": "one",
            "model": "m", "telemetry": {"latency_s": 1.0, "total_tokens": 10},
            "success_after": False, "catastrophic_after": False,
        },
        {
            "arm_id": "S2-B4", "task_id": "t2", "call_identity": "same",
            "prompt_fingerprint": "same", "response_digest": "bbb", "response": "two",
            "model": "m", "telemetry": {"latency_s": 2.0, "total_tokens": 12},
            "success_after": True, "catastrophic_after": False,
        },
    ]
    found = detect_stochastic_divergence(rows)
    assert len(found) == 1
    assert found[0]["classification"] == "STOCHASTIC_RESPONSE_DIVERGENCE"
    assert found[0]["prompt_fingerprint"] == "same"
    assert set(found[0]["response_digests"]) == {"aaa", "bbb"}
    assert found[0]["outcome_changed"] is True


def test_identical_repeated_response_is_not_divergence():
    rows = [
        {"prompt_fingerprint": "x", "response_digest": "z", "success_after": False, "catastrophic_after": False},
        {"prompt_fingerprint": "x", "response_digest": "z", "success_after": False, "catastrophic_after": False},
    ]
    assert detect_stochastic_divergence(rows) == []
