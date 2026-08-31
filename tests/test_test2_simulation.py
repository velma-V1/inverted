from inverted.test2_simulation import (
    CAUSAL,
    REQUIRES_NEW_INFERENCE,
    analyze_orderings,
    run_model_free_atlas,
)


def test_model_free_atlas_is_deterministic_and_contains_controlled_progressive_ablations():
    a = run_model_free_atlas(seed_count=3)
    b = run_model_free_atlas(seed_count=3)
    assert a == b
    assert a["trial_units"] > 1000
    assert 0.0 <= a["baseline_success_rate"] <= 1.0
    assert a["standalone_effects"]
    assert a["progressive_effects"]
    assert a["ablation_effects"]
    assert a["failure_kill_matrix"]
    assert a["saturation"]


def test_order_analysis_marks_prompt_changing_counterfactuals_as_requiring_new_inference():
    orderings = analyze_orderings(
        components=("validator", "repair", "auditor"),
        prompt_changing_components={"repair"},
    )
    assert any(row["causal_status"] == CAUSAL for row in orderings)
    assert any(row["causal_status"] == REQUIRES_NEW_INFERENCE for row in orderings)
    for row in orderings:
        if row["causal_status"] == CAUSAL:
            assert row["changes_upstream_prompt"] is False


def test_model_free_order_atlas_scores_and_ranks_every_order_without_hiding_noncausal_status():
    atlas = run_model_free_atlas(seed_count=2)
    orderings = atlas["orderings"]
    ranking = atlas["order_ranking"]
    assert len(orderings) == 120
    assert len(ranking) == len(orderings)
    assert {row["causal_status"] for row in ranking} == {CAUSAL, REQUIRES_NEW_INFERENCE}
    assert all("simulated_success_rate" in row for row in ranking)
    assert [row["rank"] for row in ranking] == list(range(1, len(ranking) + 1))
    rates = [row["simulated_success_rate"] for row in ranking]
    assert rates == sorted(rates, reverse=True)
    assert len(set(rates)) > 1
