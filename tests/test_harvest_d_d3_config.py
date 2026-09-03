import pytest

from inverted.harvest_d.d3_config import D3BudgetError, D3BudgetState, D3Phase


def test_d3_budget_is_1000_with_protected_100_call_sealed_reserve():
    budget = D3BudgetState.default()
    assert budget.total_ceiling == 1000
    assert budget.phase_ceiling(D3Phase.SEALED_CONFIRMATION) == 100
    assert budget.sealed_remaining == 100


def test_discovery_cannot_borrow_from_sealed_reserve():
    budget = D3BudgetState.default()
    with pytest.raises(D3BudgetError):
        budget.reallocate_calls(
            D3Phase.SEALED_CONFIRMATION,
            D3Phase.INFORMATION,
            1,
            reason="more power",
        )


def test_reallocation_requires_reason_and_preserves_total_ceiling():
    budget = D3BudgetState.default()
    with pytest.raises(D3BudgetError):
        budget.reallocate_calls(D3Phase.REPRESENTATION, D3Phase.INFORMATION, 1, reason="")
    budget.reallocate_calls(
        D3Phase.REPRESENTATION,
        D3Phase.INFORMATION,
        10,
        reason="representation comparison resolved",
    )
    assert sum(budget.current_ceilings.values()) == 1000
    assert budget.phase_ceiling(D3Phase.INFORMATION) == 160
    assert budget.phase_ceiling(D3Phase.REPRESENTATION) == 110


def test_budget_refuses_overrun_and_tracks_remaining_calls():
    budget = D3BudgetState.default()
    budget.reserve_call(D3Phase.BASELINE)
    assert budget.used == 1
    assert budget.remaining == 999
    assert budget.phase_remaining(D3Phase.BASELINE) == 79
    for _ in range(79):
        budget.reserve_call(D3Phase.BASELINE)
    with pytest.raises(D3BudgetError):
        budget.reserve_call(D3Phase.BASELINE)
