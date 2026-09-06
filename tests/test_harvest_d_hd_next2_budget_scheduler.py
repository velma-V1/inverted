import math
import gc
import weakref

import pytest

import inverted.harvest_d.hd_next2.budget as budget_module
from inverted.harvest_d.hd_next2.budget import CombinedActionBudget, RuntimeProfile
from inverted.harvest_d.hd_next2.scheduler import ScheduledUnit, schedule_model_blocks


def test_budget_counts_model_and_nonmodel_actions_together_and_preserves_reserve():
    budget = CombinedActionBudget(total_cap=1000, non_model_reserve=40)

    for _ in range(960):
        budget.reserve("model_call")

    with pytest.raises(ValueError, match="non-model reserve"):
        budget.reserve("model_call")

    budget.reserve("provenance_api_call")
    assert budget.total_used == 961
    assert budget.model_used == 960
    assert budget.non_model_used == 1
    assert budget.remaining_actions == 39


def test_budget_fails_closed_before_action_1001_for_any_action_kind():
    budget = CombinedActionBudget(total_cap=1000, non_model_reserve=40)
    for _ in range(1000):
        budget.reserve("non_model_action")

    with pytest.raises(ValueError, match="ceiling"):
        budget.reserve("model_call")
    assert budget.total_used == 1000


@pytest.mark.parametrize("total_cap", [0, 1001])
def test_budget_rejects_cap_outside_one_to_one_thousand(total_cap):
    with pytest.raises(ValueError, match="between 1 and 1000"):
        CombinedActionBudget(total_cap=total_cap, non_model_reserve=0)


@pytest.mark.parametrize("reserve", [-1, 1001])
def test_budget_rejects_reserve_outside_zero_to_cap(reserve):
    with pytest.raises(ValueError, match="between 0 and total action ceiling"):
        CombinedActionBudget(total_cap=1000, non_model_reserve=reserve)


def test_budget_counters_are_read_only_and_unknown_kinds_fail_closed():
    budget = CombinedActionBudget(total_cap=10, non_model_reserve=0)

    with pytest.raises((AttributeError, TypeError)):
        budget.total_used = -1
    with pytest.raises(TypeError):
        CombinedActionBudget(total_cap=10, non_model_reserve=0, total_used=-1)
    with pytest.raises(ValueError, match="unknown action kind"):
        budget.reserve("surprise_action")


def test_budget_ignores_forged_counter_attributes_for_accounting_and_reserve_caps():
    budget = CombinedActionBudget(total_cap=2, non_model_reserve=0)
    budget.reserve("model_call")

    for attribute in ("_total_used", "_model_used", "_non_model_used"):
        with pytest.raises(AttributeError):
            object.__setattr__(budget, attribute, -100)

    assert budget.total_used == 1
    assert budget.model_used == 1
    assert budget.non_model_used == 0
    budget.reserve("non_model_action")
    assert budget.total_used == 2
    with pytest.raises(ValueError, match="ceiling"):
        budget.reserve("model_call")


def test_budget_rejects_valid_looking_ledger_rollback():
    budget = CombinedActionBudget(total_cap=2, non_model_reserve=0)

    with pytest.raises(AttributeError):
        object.__setattr__(budget, "_action_ledger", ())
    budget.reserve("model_call")
    assert budget.total_used == 1


@pytest.mark.parametrize("attribute", ["total_cap", "non_model_reserve"])
def test_budget_rejects_cap_and_reserve_overwrite(attribute):
    budget = CombinedActionBudget(total_cap=2, non_model_reserve=1)

    with pytest.raises(AttributeError):
        object.__setattr__(budget, attribute, 0)

    assert budget.total_cap == 2
    assert budget.non_model_reserve == 1


def test_budget_has_no_instance_dictionary():
    assert not hasattr(CombinedActionBudget(total_cap=2, non_model_reserve=0), "__dict__")


def test_budget_registry_entry_is_cleaned_up_when_budget_is_collected():
    budget = CombinedActionBudget(total_cap=2, non_model_reserve=0)
    budget_id = id(budget)
    reference = weakref.ref(budget)
    assert budget_id in budget_module._BUDGET_REGISTRY

    del budget
    gc.collect()

    assert reference() is None
    assert budget_id not in budget_module._BUDGET_REGISTRY


def test_budget_model_aliases_and_combined_remaining_capacity():
    budget = CombinedActionBudget(total_cap=1000, non_model_reserve=40)
    for _ in range(999):
        budget.reserve("non_model_action")
    assert budget.remaining_model_actions == 1
    budget.reserve("llm_call")
    assert budget.model_used == 1
    assert budget.remaining_model_actions == 0


def test_runtime_profile_uses_local_measured_planning_anchors():
    assert RuntimeProfile.small_a().planning_seconds == pytest.approx(0.09)
    assert RuntimeProfile.qwen().planning_seconds == pytest.approx(33.97)
    assert RuntimeProfile.qwen(stress=True).planning_seconds == pytest.approx(77.22)
    assert RuntimeProfile.devstral().planning_seconds == pytest.approx(8.75)


def test_scheduler_groups_by_model_without_dropping_slow_coverage():
    units = tuple(
        ScheduledUnit(
            unit_id=f"u-{index}",
            model_key=model,
            case_id=f"case-{index % 3}",
            treatment_id=f"treatment-{index % 2}",
            replicate=index % 2,
        )
        for index, model in enumerate(("QWEN", "SMALL_A", "QWEN", "DEVSTRAL_24B", "SMALL_A", "QWEN"))
    )

    scheduled = schedule_model_blocks(units, seed=7, protected_fraction=0.0)

    assert {unit.unit_id for unit in scheduled} == {unit.unit_id for unit in units}
    positions = [unit.execution_position for unit in scheduled]
    assert positions == list(range(1, len(units) + 1))
    assert all(unit.model_block for unit in scheduled)
    assert all(unit.selection_reason for unit in scheduled)
    assert scheduled[0].planned_load_state == "planned_cold_or_load"
    assert all(unit.planned_load_state == "planned_warm_or_resident" for unit in scheduled[1:] if unit.model_block == scheduled[0].model_block)
    assert all(
        scheduled[index].model_block != scheduled[index - 1].model_block
        or scheduled[index].planned_load_state == "planned_warm_or_resident"
        for index in range(1, len(scheduled))
    )


def test_scheduler_is_seeded_and_balances_order_within_model_blocks():
    units = tuple(
        ScheduledUnit(f"u-{index}", "QWEN", f"case-{index % 3}", f"treatment-{index % 2}", index % 2)
        for index in range(12)
    )

    first = schedule_model_blocks(units, seed=41, protected_fraction=0.0)
    second = schedule_model_blocks(units, seed=41, protected_fraction=0.0)
    other = schedule_model_blocks(units, seed=42, protected_fraction=0.0)

    assert first == second
    assert [unit.unit_id for unit in first] != [unit.unit_id for unit in other]
    assert {unit.case_id for unit in first} == {"case-0", "case-1", "case-2"}
    assert {unit.treatment_id for unit in first} == {"treatment-0", "treatment-1"}
    assert all(not unit.protected_exploration for unit in first)


def test_scheduler_retains_protected_exploration_for_future_stages():
    units = tuple(ScheduledUnit(f"u-{index}", "SMALL_A", f"case-{index}", "treatment", 0) for index in range(5))

    scheduled = schedule_model_blocks(units, seed=7, protected_fraction=0.20)

    assert sum(unit.protected_exploration for unit in scheduled) >= math.ceil(len(scheduled) * 0.20)
    assert all(unit.selection_reason == "protected_exploration" for unit in scheduled if unit.protected_exploration)


def test_scheduler_balances_each_dimension_across_prefixes():
    units = tuple(
        ScheduledUnit(f"u-{index}", "QWEN", f"case-{index % 3}", f"treatment-{index % 2}", index % 2)
        for index in range(24)
    )
    scheduled = schedule_model_blocks(units, seed=7, protected_fraction=0.0)

    for prefix_length in range(1, len(scheduled) + 1):
        prefix = scheduled[:prefix_length]
        for field in ("case_id", "treatment_id", "replicate"):
            counts = [sum(getattr(unit, field) == value for unit in prefix) for value in set(getattr(unit, field) for unit in scheduled)]
            assert max(counts) - min(counts) <= 1
