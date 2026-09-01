from __future__ import annotations

from inverted.test3_s0_analysis import (
    build_candidate_s1_preregistration,
    choose_failure_conditioned_policy,
    estimate_required_task_clusters,
    grouped_fold,
    pareto_rank_candidates,
    score_fixed_policies,
    score_negative_controls,
)


def test_grouped_fold_keeps_causal_twins_together():
    assert grouped_fold("task-a", "twin-7", folds=5) == grouped_fold("task-b", "twin-7", folds=5)


def test_failure_conditioned_policy_uses_train_mapping_and_scores_holdout():
    rows = [
        {"task_id": "a", "causal_twin_id": "a", "failure_signature": "schema", "action": "repair", "success": True},
        {"task_id": "b", "causal_twin_id": "b", "failure_signature": "schema", "action": "repair", "success": True},
        {"task_id": "c", "causal_twin_id": "c", "failure_signature": "schema", "action": "retry", "success": False},
        {"task_id": "d", "causal_twin_id": "d", "failure_signature": "schema", "action": "repair", "success": True},
        {"task_id": "e", "causal_twin_id": "e", "failure_signature": "schema", "action": "repair", "success": True},
    ]
    result = choose_failure_conditioned_policy(rows, holdout_fold=grouped_fold("e", "e", folds=5))
    assert "mapping" in result
    assert result["train_rows"] + result["holdout_rows"] == 5


def test_fixed_policy_scoring_requires_explicit_policy_identity():
    action_only = [
        {"task_id": "a", "action": "retry", "success": True},
        {"task_id": "b", "action": "repair", "success": False},
    ]
    assert score_fixed_policies(action_only) == []

    explicit = [
        {"task_id": "a", "policy": "stack-A", "action": "retry", "success": True},
        {"task_id": "b", "policy": "stack-A", "action": "repair", "success": False},
        {"task_id": "c", "policy": "stack-B", "action": "retry", "success": True},
    ]
    scored = score_fixed_policies(explicit)
    assert {row["candidate"] for row in scored} == {"stack-A", "stack-B"}


def test_negative_controls_are_reproducible():
    rows = [
        {"task_id": f"t{i}", "success": bool(i % 2), "action": "repair" if i % 3 else "retry"}
        for i in range(20)
    ]
    assert score_negative_controls(rows, seed=20260901) == score_negative_controls(rows, seed=20260901)


def test_negative_controls_do_not_mislabel_identity_subsets_as_interventions():
    rows = [
        {"task_id": f"r{i}", "success": True, "action": "retry"}
        for i in range(10)
    ] + [
        {"task_id": f"v{i}", "success": False, "action": "validate"}
        for i in range(10)
    ]
    controls = {row["control"]: row for row in score_negative_controls(rows, seed=20260901)}

    switched = controls["random_action_switch"]
    assert switched["causal_status"] == "REQUIRES_NEW_INFERENCE"
    assert switched["verified_success_rate"] is None
    assert "identity_subset_replayable_rows" in switched
    assert "identity subset" in switched["reason"].lower()

    retry = controls["random_retry"]
    assert retry["causal_status"] == "REQUIRES_NEW_INFERENCE"
    assert retry["verified_success_rate"] is None
    assert retry["identity_subset_replayable_rows"] == 10
    assert retry["identity_subset_success_rate"] == 1.0


def test_pareto_frontier_excludes_dominated_candidate():
    rows = [
        {"candidate": "good", "verified_success_rate": 0.9, "catastrophe_rate": 0.0, "calls": 1, "tokens": 10, "latency_ms": 5},
        {"candidate": "bad", "verified_success_rate": 0.8, "catastrophe_rate": 0.1, "calls": 2, "tokens": 20, "latency_ms": 10},
    ]
    ranked = pareto_rank_candidates(rows)
    assert next(row for row in ranked if row["candidate"] == "good")["pareto"] is True
    assert next(row for row in ranked if row["candidate"] == "bad")["pareto"] is False


def test_power_estimator_refuses_to_invent_budget_with_too_few_clusters():
    result = estimate_required_task_clusters([{"cluster_id": "one", "effect": 0.1}], target_effect=0.03)
    assert result["status"] == "INSUFFICIENT_VARIANCE_EVIDENCE"
    assert result["recommended_clusters"] is None


def test_candidate_s1_preregistration_never_freezes_budget_or_authorizes_inference():
    prereg = build_candidate_s1_preregistration({"status": "OK", "recommended_clusters": 100})
    assert prereg["status"] == "CANDIDATE_ONLY_NOT_PREREGISTERED"
    assert prereg["tier_a_inference_authorized"] is False
    assert prereg["exact_budget"] is None
    assert prereg["holdout"] == "A"
