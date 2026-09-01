from inverted.test3_s1_analysis import derive_s1_verdict, summarize_s1


R2_FAMILIES = (
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
)


def _row(
    task,
    arm,
    success,
    *,
    family="state",
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
    seed_passed=None,
    seed_failed=None,
    final_passed=None,
    final_failed=None,
    requirement_kinds=None,
):
    return {
        "task_id": task,
        "arm_id": arm,
        "family": family,
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
        "seed_passed_requirements": list(seed_passed or []),
        "seed_failed_requirements": list(seed_failed or []),
        "final_passed_requirements": list(final_passed or []),
        "final_failed_requirements": list(final_failed or []),
        "requirement_kinds": dict(requirement_kinds or {}),
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


def _r2_family(index):
    if index == 24:
        return "repair_containment"
    return R2_FAMILIES[index % 6]


def _valid_r2_rows(outcomes=None, catastrophes=None, requirement_states=None):
    outcomes = outcomes or {}
    catastrophes = catastrophes or {}
    requirement_states = requirement_states or {}
    rows = []
    for index in range(25):
        task = f"r2-t{index:02d}"
        family = _r2_family(index)
        defaults = {arm: False for arm in ("S1-A0", "S1-A1", "S1-A2", "S1-A3")}
        defaults.update(outcomes.get(index, {}))
        for arm in ("S1-A0", "S1-A1", "S1-A2", "S1-A3"):
            state = requirement_states.get((index, arm), {})
            rows.append(_row(
                task,
                arm,
                defaults[arm],
                family=family,
                catastrophic=bool(catastrophes.get((index, arm), False)),
                first_active=(
                    "best_single_regenerate" if arm == "S1-A0" else
                    "targeted_repair" if arm == "S1-A2" else "retry"
                ),
                protocol_revision="S1-R2",
                holdout="A-R2",
                seed_passed=state.get("seed_passed", ["p1"]),
                seed_failed=state.get("seed_failed", ["f1"]),
                final_passed=state.get("final_passed", ["p1"] if not defaults[arm] else ["p1", "f1"]),
                final_failed=state.get("final_failed", ["f1"] if not defaults[arm] else []),
                requirement_kinds=state.get("requirement_kinds", {"p1": "preserve", "f1": "equal"}),
            ))
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


def test_r2_protocol_gate_requires_exact_25_tasks_200_calls_and_50_per_arm():
    summary = summarize_s1(_valid_r2_rows())
    assert summary["protocol_revision"] == "S1-R2"
    assert summary["holdout"] == "A-R2"
    assert summary["matched_task_count"] == 25
    assert summary["total_matched_physical_calls"] == 200
    assert summary["protocol_valid_for_primary_claim"] is True
    assert {row["family"] for row in summary["family_summaries"]} == set(R2_FAMILIES)

    broken = _valid_r2_rows()
    broken[0]["physical_calls_added"] = 1
    broken[0]["shadow_inference_calls"] = 0
    bad = summarize_s1(broken)
    assert bad["protocol_valid_for_primary_claim"] is False
    assert "exactly_200_physical_calls" in bad["protocol_failures"]
    assert "exactly_2_calls_per_arm_task" in bad["protocol_failures"]


def test_r2_aggregate_large_signal_uses_preregistered_5_and_3_net_win_thresholds():
    outcomes = {}
    for index in range(5):
        outcomes[index] = {"S1-A0": False, "S1-A1": True, "S1-A2": False, "S1-A3": False}
    summary = summarize_s1(_valid_r2_rows(outcomes))
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert verdict["verdict"] == "S1_R2_FIXED_ORDER_LARGE_SIGNAL"
    assert verdict["winning_arm_id"] == "S1-A1"
    assert verdict["net_wins_vs_baseline"] == 5
    assert verdict["net_wins_vs_random_control"] == 5
    assert verdict["tier_a_architecture_claim"] is True


def test_r2_category_conditional_signal_requires_same_arm_in_two_families_and_positive_aggregate():
    preservation_indices = [i for i in range(25) if _r2_family(i) == "preservation"][:2]
    containment_indices = [i for i in range(25) if _r2_family(i) == "repair_containment"][:2]
    outcomes = {
        index: {"S1-A0": False, "S1-A1": True, "S1-A2": False, "S1-A3": False}
        for index in preservation_indices + containment_indices
    }
    summary = summarize_s1(_valid_r2_rows(outcomes))
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert verdict["verdict"] == "S1_R2_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL"
    assert verdict["winning_arm_id"] == "S1-A1"
    assert set(verdict["strong_families"]) == {"preservation", "repair_containment"}
    assert verdict["tier_a_architecture_claim"] is False
    assert verdict["routing_hypothesis_supported"] is True


def test_r2_harmful_signal_requires_both_fixed_arms_to_be_materially_worse():
    outcomes = {}
    for index in range(3):
        outcomes[index] = {"S1-A0": True, "S1-A1": False, "S1-A2": False, "S1-A3": False}
    summary = summarize_s1(_valid_r2_rows(outcomes))
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert verdict["verdict"] == "S1_R2_FIXED_ORDER_NEGATIVE_OR_HARMFUL"
    assert verdict["tier_a_architecture_claim"] is False


def test_r2_valid_null_is_non_decisive_and_cannot_rule_out_small_effect():
    outcomes = {index: {arm: True for arm in ("S1-A0", "S1-A1", "S1-A2", "S1-A3")} for index in range(25)}
    verdict = derive_s1_verdict(summarize_s1(_valid_r2_rows(outcomes)), full_power_clusters=260)
    assert verdict["verdict"] == "S1_R2_SCREEN_NON_DECISIVE"
    assert verdict["cannot_rule_out_target_effect"] is True
    assert verdict["tier_a_architecture_claim"] is False


def test_r2_containment_metrics_record_repairs_regressions_and_new_failures():
    index = next(i for i in range(25) if _r2_family(i) == "repair_containment")
    states = {
        (index, "S1-A1"): {
            "seed_passed": ["p1", "p2"],
            "seed_failed": ["f1"],
            "final_passed": ["p2", "f1"],
            "final_failed": ["p1"],
            "requirement_kinds": {"p1": "preserve", "p2": "equal", "f1": "equal"},
        }
    }
    summary = summarize_s1(_valid_r2_rows(requirement_states=states))
    family = next(row for row in summary["family_summaries"] if row["family"] == "repair_containment")
    a1 = next(row for row in family["arm_summaries"] if row["arm_id"] == "S1-A1")
    assert a1["requirements_repaired"] >= 1
    assert a1["requirements_regressed"] >= 1
    assert a1["new_failures_introduced"] >= 1
    assert a1["preservation_violations"] >= 1
