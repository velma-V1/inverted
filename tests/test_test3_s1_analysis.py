from inverted.test3_s1_analysis import derive_s1_verdict, summarize_s1


def _row(task, arm, success, *, catastrophic=False, calls=1, tokens=100, complete=True):
    return {
        "task_id": task,
        "arm_id": arm,
        "success": success,
        "catastrophic": catastrophic,
        "physical_calls_added": calls,
        "total_tokens": tokens,
        "complete": complete,
    }


def test_primary_analysis_uses_only_tasks_completed_by_every_arm():
    rows = []
    for task in ("t1", "t2", "t3"):
        rows.extend([
            _row(task, "S1-A0", task == "t1"),
            _row(task, "S1-A1", True, calls=2),
            _row(task, "S1-A2", task != "t3", calls=2),
            _row(task, "S1-A3", False, calls=2),
        ])
    rows.append(_row("partial", "S1-A0", True))
    rows.append(_row("partial", "S1-A1", True, complete=False))

    summary = summarize_s1(rows, baseline_arm="S1-A0", random_control_arm="S1-A3")
    assert summary["matched_task_ids"] == ["t1", "t2", "t3"]
    assert summary["matched_task_count"] == 3
    a1 = next(row for row in summary["pairwise_effects"] if row["arm_id"] == "S1-A1" and row["reference_arm_id"] == "S1-A0")
    assert a1["wins_created"] == 2
    assert a1["wins_destroyed"] == 0
    assert a1["net_wins"] == 2
    assert a1["catastrophes_added"] == 0
    assert a1["mean_physical_calls"] == 2.0


def test_strong_screen_requires_baseline_gain_random_gain_and_no_catastrophe():
    rows = []
    baseline = [True, False, False, False, True, False]
    fixed = [True, True, True, False, True, False]
    alternate = [True, False, True, False, True, False]
    random = [True, False, False, False, True, False]
    for i, task in enumerate([f"t{x}" for x in range(6)]):
        rows.extend([
            _row(task, "S1-A0", baseline[i]),
            _row(task, "S1-A1", fixed[i], calls=2),
            _row(task, "S1-A2", alternate[i], calls=2),
            _row(task, "S1-A3", random[i], calls=2),
        ])
    summary = summarize_s1(rows, baseline_arm="S1-A0", random_control_arm="S1-A3")
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert verdict["verdict"] == "S1_STRONG_FIXED_ORDER_SIGNAL"
    assert verdict["winning_arm_id"] == "S1-A1"
    assert verdict["tier_a_architecture_claim"] is True


def test_underpowered_null_screen_cannot_rule_out_small_effect():
    rows = []
    for task in [f"t{x}" for x in range(6)]:
        for arm in ("S1-A0", "S1-A1", "S1-A2", "S1-A3"):
            rows.append(_row(task, arm, True, calls=1 if arm == "S1-A0" else 2))
    summary = summarize_s1(rows, baseline_arm="S1-A0", random_control_arm="S1-A3")
    verdict = derive_s1_verdict(summary, full_power_clusters=260)
    assert verdict["verdict"] == "S1_SCREEN_NON_DECISIVE"
    assert verdict["cannot_rule_out_target_effect"] is True
    assert verdict["full_power_cluster_requirement"] == 260
    assert verdict["tier_a_architecture_claim"] is False
