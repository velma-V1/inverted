from inverted.models import MockModelAdapter
from inverted.test2_local import (
    LOCAL_MODELS,
    LOCAL_PHASE_LIMITS,
    PROGRESSIVE_PIPELINES,
    BoundedModelCaller,
    build_local_plan,
    build_progressive_role_assignments,
    run_local_campaign,
)
from inverted.test2_types import PhysicalCallBudget


def test_local_plan_uses_exact_models_and_never_exceeds_480_physical_calls():
    plan = build_local_plan()
    assert tuple(plan.models) == LOCAL_MODELS
    assert sum(LOCAL_PHASE_LIMITS.values()) == 480
    assert LOCAL_PHASE_LIMITS["repair_factorial"] == 100
    assert LOCAL_PHASE_LIMITS["progressive_holdout"] == 100
    assert plan.max_physical_calls == 480
    assert plan.planned_max_physical_calls <= 480


def test_progressive_role_assignments_replace_one_role_at_a_time():
    rows = build_progressive_role_assignments(
        best_single="single",
        formalizer="form",
        executor="exec",
        repairer="repair",
        auditor="audit",
    )
    assert tuple(row["pipeline"] for row in rows) == PROGRESSIVE_PIPELINES[:5]
    assert rows[0]["roles"] == {
        "formalizer": "single", "executor": "single", "repairer": "single", "auditor": "single"
    }
    assert rows[1]["roles"]["formalizer"] == "form"
    assert rows[1]["roles"]["executor"] == "single"
    assert rows[2]["roles"]["executor"] == "exec"
    assert rows[3]["roles"]["repairer"] == "repair"
    assert rows[4]["roles"]["auditor"] == "audit"


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


def test_full_mock_campaign_stays_bounded_and_records_progressive_and_raw_evidence():
    models = [MockModelAdapter(model=name) for name in LOCAL_MODELS]
    result = run_local_campaign(models, run_id="mock-test2", hard_limit=480)
    assert result["physical_model_calls"] <= 480
    pipelines = {
        row.get("pipeline")
        for row in result["records"]
        if row.get("phase") == "progressive_holdout"
    }
    assert set(PROGRESSIVE_PIPELINES) <= pipelines
    assert result["candidates"]
    assert result["events"]
    assert all("phase" in row and "task_id" in row for row in result["events"])
    assert any(row.get("source") == "fixed_audit_bank" for row in result["candidates"])
