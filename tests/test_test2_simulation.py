from inverted.test2_postanalysis import (
    candidate_independence_strata,
    failure_streak_quality_posterior,
    mutation_boundary_analysis,
    retry_repair_thresholds,
)
from inverted.test2_production_orders import run_production_order_atlas
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


def test_model_free_atlas_separately_ranks_all_production_orders_without_oracle():
    atlas = run_production_order_atlas(seed_count=2)
    orderings = atlas["orderings"]
    ranking = atlas["order_ranking"]
    slices = atlas["order_slice_ranking"]
    assert len(orderings) == 24
    assert len(ranking) == 24
    assert slices
    assert [row["rank"] for row in ranking] == list(range(1, 25))
    assert all("oracle_auditor" not in row["components"] for row in ranking)
    assert all("oracle_auditor" not in row["order"] for row in ranking)
    assert all(row["evidence_scope"] == "PRODUCTION_ORDER_HYPOTHESIS" for row in ranking)
    assert all(row["production_eligible"] is True for row in ranking)
    assert {row["causal_status"] for row in ranking} == {CAUSAL, REQUIRES_NEW_INFERENCE}


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


def test_candidate_independence_is_stratified_and_repair_thresholds_match_retry_value():
    atlas = run_model_free_atlas(seed_count=4)
    trials = atlas["base_cell_records"]
    strata = candidate_independence_strata(trials)
    quality_rows = [row for row in strata if row["slice_type"] == "quality"]
    assert quality_rows
    assert {row["quality"] for row in quality_rows} == {0.20, 0.40, 0.60, 0.80, 0.95}
    assert all("observed_to_independent_failure_ratio" in row for row in quality_rows)
    assert all("success_correlation_attempt_1_2" in row for row in quality_rows)

    thresholds = retry_repair_thresholds(trials)
    overall = [row for row in thresholds if row["slice_type"] == "overall"]
    assert [row["next_attempt"] for row in overall] == [2, 3]
    saturation = atlas["candidate_saturation"]
    assert overall[0]["repair_break_even_recovery_rate"] == saturation[1]["conditional_recovery_rate"]
    assert overall[1]["repair_break_even_recovery_rate"] == saturation[2]["conditional_recovery_rate"]
    assert any(row["slice_type"] == "quality" for row in thresholds)
    assert any(row["slice_type"] == "fault" for row in thresholds)


def test_failure_streak_is_preserved_as_a_quality_escalation_signal():
    atlas = run_model_free_atlas(seed_count=4)
    posterior = failure_streak_quality_posterior(atlas["base_cell_records"], low_quality_max=0.40)
    assert [row["consecutive_failures"] for row in posterior] == [0, 1, 2, 3]
    assert posterior[0]["low_quality_probability"] <= posterior[1]["low_quality_probability"]
    assert posterior[1]["low_quality_probability"] <= posterior[2]["low_quality_probability"]
    assert posterior[2]["low_quality_probability"] <= posterior[3]["low_quality_probability"]
    assert all("quality_distribution" in row for row in posterior)


def test_revalidation_after_each_retry_preserves_wins_and_removes_catastrophic_escape():
    atlas = run_model_free_atlas(seed_count=4)
    rows = {row["stage"]: row for row in mutation_boundary_analysis(atlas["base_cell_records"])}
    raw2 = rows["RETRY_2_WITHOUT_REVALIDATION"]
    checked2 = rows["RETRY_2_THEN_REVALIDATE"]
    raw3 = rows["RETRY_3_WITHOUT_REVALIDATION"]
    checked3 = rows["RETRY_3_THEN_REVALIDATE"]
    assert checked2["successes"] == raw2["successes"]
    assert checked3["successes"] == raw3["successes"]
    assert checked2["catastrophic_escapes"] == 0
    assert checked3["catastrophic_escapes"] == 0
    assert checked2["catastrophic_escapes"] <= raw2["catastrophic_escapes"]
    assert checked3["catastrophic_escapes"] <= raw3["catastrophic_escapes"]
    assert rows["ORACLE_REPAIR_THEN_FINAL_AUTHORITY"]["success_rate"] == 1.0