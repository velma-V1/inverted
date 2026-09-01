import pytest

from inverted.test3_s2_budget import CombinedActionBudget


def test_s2_combined_action_budget_is_single_shared_fail_closed_720_budget():
    budget = CombinedActionBudget(720)
    for _ in range(719):
        budget.reserve("model_call")
    budget.reserve("api_call")

    snap = budget.snapshot()
    assert snap["limit"] == 720
    assert snap["combined_used"] == 720
    assert snap["remaining"] == 0
    assert snap["by_kind"] == {"model_call": 719, "api_call": 1}

    with pytest.raises(RuntimeError, match="combined action budget"):
        budget.reserve("tool_call")


def test_repository_absolute_ceiling_is_enforced_even_if_constructor_requests_more():
    with pytest.raises(ValueError, match="1000"):
        CombinedActionBudget(1001)
