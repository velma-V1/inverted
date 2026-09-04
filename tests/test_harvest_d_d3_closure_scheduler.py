import pytest

from inverted.harvest_d.d3_closure_scheduler import (
    ClosureBudget,
    ClosureDecision,
    ClosureScheduler,
)


def test_superior_deepens_instead_of_repeating_screen():
    scheduler = ClosureScheduler()
    scheduler.observe("m1", ClosureDecision.SUPERIOR)
    assert scheduler.next_mode("m1") == "DEEPEN_OR_ABLATE"


def test_harmful_allows_only_contradiction_check():
    scheduler = ClosureScheduler()
    scheduler.observe("m1", ClosureDecision.HARMFUL)
    assert scheduler.allowed_kinds("m1") == ("CONTRADICTION_CHECK",)


def test_futile_stops_ordinary_spending():
    scheduler = ClosureScheduler()
    scheduler.observe("m1", ClosureDecision.FUTILE)
    assert scheduler.next_mode("m1") is None


def test_unresolved_requests_discrimination():
    scheduler = ClosureScheduler()
    scheduler.observe("m1", ClosureDecision.UNRESOLVED)
    assert scheduler.next_mode("m1") == "DISCRIMINATE"


def test_budget_reallocates_unsealed_but_never_borrows_sealed():
    budget = ClosureBudget.default()
    before_sealed = budget.ceiling("C7")
    budget.reallocate("C2", "C3", 4, reason="C2 resolved; C3 unresolved")
    assert budget.ceiling("C2") == 32
    assert budget.ceiling("C3") == 40
    assert budget.ceiling("C7") == before_sealed == 48
    with pytest.raises(ValueError):
        budget.reallocate("C7", "C3", 1, reason="not allowed")
    assert budget.total_ceiling == 200
