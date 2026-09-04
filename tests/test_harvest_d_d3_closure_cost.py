from __future__ import annotations

from pathlib import Path

from inverted.harvest_d.d3_closure_cost import (
    CostBudgetState,
    CostClass,
    CostObservation,
    classify_cost,
    load_cost_profile,
    sample_allowance,
)


PROFILE = Path("configs/harvest-d-local-model-cost-profile.json")


def test_current_hardware_profile_encodes_95_gib_residency_cliff():
    profile = load_cost_profile(PROFILE)
    assert profile.residency_cliff_gib == 9.5


def test_system_only_work_is_free_and_does_not_consume_physical_calls():
    profile = load_cost_profile(PROFILE)
    observation = CostObservation(system_only=True)
    assert classify_cost(observation, profile) is CostClass.FREE


def test_tiny_fast_model_can_be_near_free():
    profile = load_cost_profile(PROFILE)
    observation = CostObservation(
        installed_size_gib=1.5,
        tiny_model=True,
        median_latency_s=0.4,
        thinking=False,
    )
    assert classify_cost(observation, profile) is CostClass.NEAR_FREE


def test_model_just_under_residency_cliff_is_not_treated_like_model_over_cliff():
    profile = load_cost_profile(PROFILE)
    resident = CostObservation(installed_size_gib=9.4, median_latency_s=8.0, thinking=False)
    spilled = CostObservation(installed_size_gib=9.6, median_latency_s=8.0, thinking=False)

    assert classify_cost(resident, profile) in {CostClass.FAST, CostClass.MEDIUM}
    assert classify_cost(spilled, profile) is CostClass.VERY_EXPENSIVE


def test_thinking_or_runtime_spill_can_raise_cost_class():
    profile = load_cost_profile(PROFILE)
    thinking = CostObservation(installed_size_gib=9.4, median_latency_s=70.0, thinking=True)
    offloaded = CostObservation(installed_size_gib=8.0, median_latency_s=70.0, offload_observed=True)

    assert classify_cost(thinking, profile) is CostClass.VERY_EXPENSIVE
    assert classify_cost(offloaded, profile) is CostClass.VERY_EXPENSIVE


def test_same_time_budget_allows_many_more_cheap_calls_than_expensive_calls():
    near_free = sample_allowance(available_seconds=600.0, expected_call_seconds=0.5, hard_call_cap=5000)
    medium = sample_allowance(available_seconds=600.0, expected_call_seconds=10.0, hard_call_cap=5000)
    expensive = sample_allowance(available_seconds=600.0, expected_call_seconds=80.0, hard_call_cap=5000)

    assert near_free > medium > expensive
    assert near_free >= 1000
    assert expensive <= 7


def test_budget_vector_keeps_development_and_confirmation_reserves_separate():
    budget = CostBudgetState(
        max_physical_calls=1000,
        max_inference_seconds=1000.0,
        confirmation_reserved_calls=100,
        confirmation_reserved_seconds=250.0,
    )

    budget.reserve_model_call(expected_seconds=10.0, confirmation=False)
    assert budget.physical_calls_used == 1
    assert budget.inference_seconds_reserved == 10.0
    assert budget.confirmation_calls_used == 0

    budget.record_system_only_operation()
    assert budget.system_only_operations == 1
    assert budget.physical_calls_used == 1

    # Development may not borrow the protected confirmation time/call reserve.
    assert budget.development_calls_available == 899
    assert budget.development_seconds_available == 740.0
