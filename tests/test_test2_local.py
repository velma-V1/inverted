from inverted.models import MockModelAdapter
from inverted.test2_local import (
    LOCAL_MODELS,
    LOCAL_PHASE_LIMITS,
    BoundedModelCaller,
    build_local_plan,
)
from inverted.test2_types import PhysicalCallBudget


def test_local_plan_uses_exact_models_and_never_exceeds_480_physical_calls():
    plan = build_local_plan()
    assert tuple(plan.models) == LOCAL_MODELS
    assert sum(LOCAL_PHASE_LIMITS.values()) == 480
    assert plan.max_physical_calls == 480
    assert plan.planned_max_physical_calls <= 480


def test_bounded_caller_reuses_identical_call_without_consuming_budget_twice():
    budget = PhysicalCallBudget(max_calls=2)
    caller = BoundedModelCaller(budget)
    model = MockModelAdapter(model="m")
    messages = [{"role": "user", "content": "same"}]
    context = {"run_id": "r", "trial_id": "t", "call_id": "c", "mock_text": '{"ok":true}'}

    first = caller.complete(model, messages, role="formalizer", context=context, response_schema={"type": "object"})
    second = caller.complete(model, messages, role="formalizer", context=context, response_schema={"type": "object"})

    assert first.text == second.text
    assert budget.physical_calls == 1
    assert budget.cache_hits == 1
    assert second.cache_hit is True


def test_bounded_caller_does_not_reuse_when_upstream_prompt_changes_and_preserves_exact_content():
    budget = PhysicalCallBudget(max_calls=3)
    caller = BoundedModelCaller(budget)
    model = MockModelAdapter(model="m")

    a = caller.complete(
        model,
        [{"role": "user", "content": "alpha"}],
        role="repairer",
        context={"run_id": "r", "trial_id": "a", "call_id": "a", "mock_text": "RAW-A"},
    )
    b = caller.complete(
        model,
        [{"role": "user", "content": "beta"}],
        role="repairer",
        context={"run_id": "r", "trial_id": "b", "call_id": "b", "mock_text": "RAW-B"},
    )

    assert budget.physical_calls == 2
    assert a.prompt == [{"role": "user", "content": "alpha"}]
    assert a.response == "RAW-A"
    assert b.prompt == [{"role": "user", "content": "beta"}]
    assert b.response == "RAW-B"
