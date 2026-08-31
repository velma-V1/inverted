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
    assert a["failure_recovery_matrix"]
    assert a["saturation"]
    assert len(a["candidate_saturation"]) == 3
    assert a["candidate_independence"]
    assert a["base_cell_records"]
    assert a["component_slice_effects"]
    assert a["order_slice_ranking"]


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


def test_retry_repair_overlap_is_not_mislabeled_as_harm_and_retry_saturation_is_measured():
    atlas = run_model_free_atlas(seed_count=3)
    pair = next(
        row for row in atlas["pairwise_interactions"]
        if {row["component_a"], row["component_b"]} == {"retry", "targeted_repair"}
    )
    assert pair["success_rate"] >= max(pair["component_a_success_rate"], pair["component_b_success_rate"])
    assert pair["classification"] == "SATURATION_OR_OVERLAP"

    saturation = atlas["candidate_saturation"]
    assert [row["attempts_available"] for row in saturation] == [1, 2, 3]
    assert saturation[1]["cumulative_success_rate"] >= saturation[0]["cumulative_success_rate"]
    assert saturation[2]["cumulative_success_rate"] >= saturation[1]["cumulative_success_rate"]
    assert "observed_no_success_in_3_rate" in atlas["candidate_independence"]
    assert "independent_expected_no_success_in_3_rate" in atlas["candidate_independence"]


def test_failure_recovery_and_slice_outputs_preserve_task_specific_information():
    atlas = run_model_free_atlas(seed_count=2)
    recovery = atlas["failure_recovery_matrix"]
    assert recovery
    assert any(row.get("recovered_by_retry", 0) > 0 for row in recovery)
    assert any(row.get("recovered_by_targeted_repair", 0) > 0 for row in recovery)

    component_slices = atlas["component_slice_effects"]
    slice_types = {row["slice_type"] for row in component_slices}
    assert {"family", "complexity", "quality", "family_complexity_quality"}.issubset(slice_types)

    order_slices = atlas["order_slice_ranking"]
    assert order_slices
    assert any(row["slice_type"] == "family" for row in order_slices)
    assert any(row["slice_type"] == "family_complexity_quality" for row in order_slices)
    assert all("rank_within_slice" in row for row in order_slices)
