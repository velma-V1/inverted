from inverted.test2_analysis import (
    OutcomeSnapshot,
    classify_transition,
    minimum_sufficient_stack,
    model_complementarity,
    pareto_frontier,
    router_regret,
    summarize_component_effects,
)


def test_transition_classifier_separates_recovery_blocking_displacement_and_regression():
    fail_a = OutcomeSnapshot(False, failure_signature="wrong_value")
    fail_b = OutcomeSnapshot(False, failure_signature="omission")
    blocked = OutcomeSnapshot(False, blocked=True, failure_signature="wrong_value")
    success = OutcomeSnapshot(True)
    catastrophic = OutcomeSnapshot(False, catastrophic=True, failure_signature="forbidden")
    safe_fail = OutcomeSnapshot(False, failure_signature="forbidden")

    assert classify_transition(fail_a, success) == "FAIL_TO_SUCCESS"
    assert classify_transition(success, fail_a) == "SUCCESS_TO_FAIL"
    assert classify_transition(fail_a, blocked) == "FAIL_TO_BLOCKED"
    assert classify_transition(fail_a, fail_b) == "FAIL_TO_DIFFERENT_FAIL"
    assert classify_transition(catastrophic, safe_fail) == "CATASTROPHIC_TO_SAFE"
    assert classify_transition(safe_fail, catastrophic) == "SAFE_TO_CATASTROPHIC"
    assert classify_transition(success, success) == "SUCCESS_TO_SUCCESS"
    assert classify_transition(fail_a, fail_a) == "FAIL_TO_FAIL"


def test_component_effect_summary_counts_wins_prevention_displacement_and_net_value():
    pairs = [
        (OutcomeSnapshot(False, failure_signature="x"), OutcomeSnapshot(True)),
        (OutcomeSnapshot(True), OutcomeSnapshot(False, failure_signature="y")),
        (OutcomeSnapshot(False, failure_signature="x"), OutcomeSnapshot(False, blocked=True, failure_signature="x")),
        (OutcomeSnapshot(False, failure_signature="x"), OutcomeSnapshot(False, failure_signature="z")),
        (OutcomeSnapshot(False, catastrophic=True, failure_signature="c"), OutcomeSnapshot(False, failure_signature="c")),
    ]
    summary = summarize_component_effects(pairs)
    assert summary["wins_created"] == 1
    assert summary["wins_destroyed"] == 1
    assert summary["net_wins"] == 0
    assert summary["failures_prevented"] == 1
    assert summary["failures_displaced"] == 1
    assert summary["catastrophics_removed"] == 1


def test_minimum_sufficient_stack_finds_smallest_within_requested_gap():
    stacks = [
        {"name": "full", "components": 8, "success_rate": 0.971},
        {"name": "six", "components": 6, "success_rate": 0.970},
        {"name": "five", "components": 5, "success_rate": 0.968},
        {"name": "four", "components": 4, "success_rate": 0.932},
    ]
    out = minimum_sufficient_stack(stacks, gaps=(0.005, 0.01, 0.02))
    assert out["within_0.005"]["name"] == "five"
    assert out["within_0.01"]["name"] == "five"
    assert out["within_0.02"]["name"] == "five"


def test_pareto_frontier_removes_strictly_dominated_architectures():
    rows = [
        {"name": "a", "success_rate": 0.95, "calls": 2, "latency_s": 2.0},
        {"name": "b", "success_rate": 0.96, "calls": 2, "latency_s": 2.0},
        {"name": "c", "success_rate": 0.94, "calls": 1, "latency_s": 1.0},
    ]
    names = {x["name"] for x in pareto_frontier(rows)}
    assert names == {"b", "c"}


def test_router_regret_and_model_complementarity_capture_specialization_value():
    outcomes = {
        "task1": {"A": True, "B": False},
        "task2": {"A": False, "B": True},
        "task3": {"A": True, "B": True},
        "task4": {"A": False, "B": False},
    }
    comp = model_complementarity(outcomes, "A", "B")
    assert comp["a_only"] == 1
    assert comp["b_only"] == 1
    assert comp["both_success"] == 1
    assert comp["both_fail"] == 1

    routed = {"task1": "A", "task2": "A", "task3": "B", "task4": "B"}
    regret = router_regret(outcomes, routed)
    assert regret["oracle_successes"] == 3
    assert regret["routed_successes"] == 2
    assert regret["regret_successes"] == 1
