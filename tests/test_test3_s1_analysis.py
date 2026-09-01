from inverted.test3_s1_analysis import derive_s1_verdict, summarize_s1


def _row(
    task,
    arm,
    success,
    *,
    catastrophic=False,
    calls=2,
    tokens=100,
    complete=True,
    seed_failure_verified=True,
    active=1,
    shadow=1,
    first_active="retry",
    protocol_revision="S1-R1",
    holdout="A-R1",
):
    return {
        "task_id": task,
        "arm_id": arm,
        "success": success,
        "catastrophic": catastrophic,
        "physical_calls_added": calls,
        "total_tokens": tokens,
        "complete": complete,
        "seed_failure_verified": seed_failure_verified,
        "active_inference_calls": active,
        "shadow_inference_calls": shadow,
        "first_active_component": first_active,
        "protocol_revision": protocol_revision,
        "holdout": holdout,
        "cache_hits": 0,
    }


def _valid_rows(outcomes=None):
    outcomes = outcomes or {}
    rows = []
    for index in range(10):
        task = f"t{index}"
        defaults = {
            "S1-A0": False,
            "S1-A1": False,
            "S1-A2": False,
            "S1-A3": False,
        }
        defaults.update(outcomes.get(index, {}))
        rows.extend([
            _row(task, "S1-A0", defaults["S1-A0"], first_active="best_single_regenerate"),
            _row(task, "S1-A1", defaults["S1-A1"], first_active="retry"),
            _row(task, "S1-A2", defaults["S1-A2"], first_active="targeted_repair"),
            _row(task, "S1-A3", defaults["S1-A3"], first_active="retry"),
        ])
    return rows


def test_primary_analysis_uses_only_tasks_completed_by_every_arm():
    rows = _valid_rows()
    rows.append(_row("partial", "S1-A0", True))
    rows.append(_row("partial", "S1-A1", True, complete=False))

    summary = summarize_s1(rows, baseline_arm="S1-A0", random_control_arm="S1-A3")
    assert summary["matched_task_count"] == 10
    assert summary["protocol_valid_for_primary_claim"] is True
    assert summary["total_matched_physical_calls"] == 80
    assert summary["intervention_exposure"]["all_seed_failures_verified"] is True
    assert summary["intervention_exposure"]["all_arm_tasks_have_active_intervention"] is True
    assert summary["intervention_exposure"]["distinct_fixed_first_active_components"] >= 2


def test_legacy_24_call_six_task_shape_is_invalid_for_primary_s1_claim():
    rows = []
    for index in range(6):
        task = f"legacy-{index}"
        rows.extend([
            _row(task, "S1-A0", True, calls=1, active=1, shadow=0, protocol_revision="S1", holdout="A"),
            _row(task, "S1-A1", True, calls=1, active=1, shadow=0, protocol_revision="S1", holdout="A"),
            _row(task, "S1-A2", True, calls=1, active=1, shadow=0, protocol_revision="S1", holdout="A"),
            _row(task, "S1-A3", True, calls=1, active=1, shadow=0, protocol_revision="S1", holdout="A"),
        ])
    summary = summarize_s1(rows)
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert summary["total_matched_physical_calls"] == 24
    assert summary["protocol_valid_for_primary_claim"] is False
    assert "exactly_80_physical_calls" in summary["protocol_failures"]
    assert verdict["verdict"] == "S1_INVALID_INTERVENTION_EXPOSURE"
    assert verdict["tier_a_architecture_claim"] is False


def test_strong_screen_requires_valid_r1_contract_baseline_gain_random_gain_and_no_catastrophe():
    outcomes = {
        0: {"S1-A0": True, "S1-A1": True, "S1-A2": True, "S1-A3": True},
        1: {"S1-A0": False, "S1-A1": True, "S1-A2": False, "S1-A3": False},
        2: {"S1-A0": False, "S1-A1": True, "S1-A2": True, "S1-A3": False},
        3: {"S1-A0": False, "S1-A1": False, "S1-A2": False, "S1-A3": False},
        4: {"S1-A0": True, "S1-A1": True, "S1-A2": True, "S1-A3": True},
    }
    summary = summarize_s1(_valid_rows(outcomes))
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert summary["protocol_valid_for_primary_claim"] is True
    assert verdict["verdict"] == "S1_STRONG_FIXED_ORDER_SIGNAL"
    assert verdict["winning_arm_id"] == "S1-A1"
    assert verdict["tier_a_architecture_claim"] is True


def test_valid_underpowered_null_screen_cannot_rule_out_small_effect():
    rows = _valid_rows({index: {arm: True for arm in ("S1-A0", "S1-A1", "S1-A2", "S1-A3")} for index in range(10)})
    summary = summarize_s1(rows)
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert summary["protocol_valid_for_primary_claim"] is True
    assert verdict["verdict"] == "S1_SCREEN_NON_DECISIVE"
    assert verdict["cannot_rule_out_target_effect"] is True
    assert verdict["full_power_cluster_requirement"] == 260
    assert verdict["tier_a_architecture_claim"] is False
