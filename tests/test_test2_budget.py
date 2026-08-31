import pytest

from inverted.test2_types import (
    CallIdentity,
    PhysicalCallBudget,
    PhysicalCallLimitExceeded,
)


def test_physical_call_budget_refuses_call_over_hard_limit():
    budget = PhysicalCallBudget(max_calls=2)
    budget.consume("a")
    budget.consume("b")
    assert budget.physical_calls == 2
    with pytest.raises(PhysicalCallLimitExceeded):
        budget.consume("c")
    assert budget.physical_calls == 2


def test_cache_hit_does_not_consume_physical_call_budget():
    budget = PhysicalCallBudget(max_calls=1)
    budget.note_cache_hit("same")
    assert budget.physical_calls == 0
    assert budget.cache_hits == 1
    budget.consume("real")
    assert budget.physical_calls == 1


def test_call_identity_is_stable_and_sensitive_to_every_inference_input():
    messages = [{"role": "user", "content": "x"}]
    base = CallIdentity.build(
        model="m1",
        role="auditor",
        messages=messages,
        settings={"temperature": 0, "max_tokens": 128},
        response_schema={"type": "object"},
    )
    same = CallIdentity.build(
        model="m1",
        role="auditor",
        messages=[{"role": "user", "content": "x"}],
        settings={"max_tokens": 128, "temperature": 0},
        response_schema={"type": "object"},
    )
    assert base.digest == same.digest

    changed = [
        CallIdentity.build("m2", "auditor", messages, {"temperature": 0, "max_tokens": 128}, {"type": "object"}),
        CallIdentity.build("m1", "executor", messages, {"temperature": 0, "max_tokens": 128}, {"type": "object"}),
        CallIdentity.build("m1", "auditor", [{"role": "user", "content": "y"}], {"temperature": 0, "max_tokens": 128}, {"type": "object"}),
        CallIdentity.build("m1", "auditor", messages, {"temperature": 0.1, "max_tokens": 128}, {"type": "object"}),
        CallIdentity.build("m1", "auditor", messages, {"temperature": 0, "max_tokens": 128}, {"type": "array"}),
    ]
    assert all(item.digest != base.digest for item in changed)
