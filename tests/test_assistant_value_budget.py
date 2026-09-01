import pytest

from inverted.assistant_value import TEST_CALL_CAPS
from inverted.assistant_value.budget import CallBudgetExceeded, PhysicalCallBudget
from inverted.assistant_value.authority import planned_authority_calls
from inverted.assistant_value.evidence_trust import planned_evidence_calls
from inverted.assistant_value.ground_truth_isolation import planned_ground_truth_calls
from inverted.assistant_value.long_horizon import planned_long_horizon_calls


def test_preregistered_hard_caps_are_exact():
    assert TEST_CALL_CAPS == {
        "long_horizon": 1152,
        "evidence_trust": 1080,
        "authority": 1152,
        "ground_truth_isolation": 1080,
    }


def test_default_three_model_plans_fit_caps():
    assert planned_long_horizon_calls(model_count=3) == 972
    assert planned_evidence_calls(model_count=3) == 1080
    assert planned_authority_calls(model_count=3) == 1080
    assert planned_ground_truth_calls(model_count=3) == 1080
    assert planned_long_horizon_calls(3) <= TEST_CALL_CAPS["long_horizon"]
    assert planned_evidence_calls(3) <= TEST_CALL_CAPS["evidence_trust"]
    assert planned_authority_calls(3) <= TEST_CALL_CAPS["authority"]
    assert planned_ground_truth_calls(3) <= TEST_CALL_CAPS["ground_truth_isolation"]


def test_physical_call_budget_refuses_cap_plus_one_and_counts_failed_attempts():
    budget = PhysicalCallBudget("evidence_trust", cap=2)
    first = budget.reserve(call_id="c1", trial_id="t1", role="direct")
    second = budget.reserve(call_id="c2", trial_id="t2", role="direct")
    assert first == 1
    assert second == 2
    assert budget.used == 2
    assert budget.remaining == 0

    with pytest.raises(CallBudgetExceeded):
        budget.reserve(call_id="c3", trial_id="t3", role="direct")

    snapshot = budget.to_dict()
    assert snapshot["used"] == 2
    assert snapshot["remaining"] == 0
    assert len(snapshot["reservations"]) == 2
