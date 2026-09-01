from __future__ import annotations

import json

import pytest

from inverted.models import MockModelAdapter
from inverted.system_executor import generate_candidate
from inverted.test2_types import PhysicalCallBudget
from inverted.test3_s1_cases import build_holdout_a_r1, build_holdout_a_r2, r2_arm_order
from inverted.test3_s1_runtime import (
    S1_CALLS_PER_ARM_TASK,
    matched_task_limit,
    public_failure_feedback,
    run_arm_task,
    run_s1_screen,
    worst_case_calls_for_arm,
)


class QueueModel(MockModelAdapter):
    def __init__(self, model: str, responses: dict[str, list[str]]):
        super().__init__(model=model)
        self.responses = {key: list(values) for key, values in responses.items()}
        self.max_retries = 0

    def complete(self, messages, *, role, context):
        values = self.responses.setdefault(role, [])
        text = values.pop(0) if values else '{"actions":[]}'
        return super().complete(messages, role=role, context={**context, "mock_text": text})


def _actions_json(candidate) -> str:
    return json.dumps({"actions": [action.to_dict() for action in candidate.actions]})


def _arms(cap: int = 20):
    return [
        {"arm_id": "S1-A0", "role": "best_single_model_baseline", "order": None, "physical_call_cap": cap},
        {"arm_id": "S1-A1", "role": "current_best_fixed_hybrid", "order": "requirement_validator -> retry -> targeted_repair -> final_validator", "physical_call_cap": cap},
        {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "requirement_validator -> targeted_repair -> final_validator -> retry", "physical_call_cap": cap},
        {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "retry -> targeted_repair -> final_validator -> requirement_validator", "physical_call_cap": cap},
    ]


def test_r1_budget_contract_is_two_calls_per_arm_task_and_ten_matched_tasks():
    arms = _arms()
    assert S1_CALLS_PER_ARM_TASK == 2
    assert all(worst_case_calls_for_arm(arm) == 2 for arm in arms)
    assert matched_task_limit(arms, available_cases=10) == 10


def test_public_failure_feedback_strips_internal_requirement_fields():
    case = next(case for case in build_holdout_a_r1() if any(req.critical for req in case.task.requirements))
    critical_id = next(req.id for req in case.task.requirements if req.critical)
    candidate = generate_candidate(case.task, 0.0, 991000)
    feedback = public_failure_feedback(case.task, candidate, [critical_id])
    text = json.dumps(feedback, sort_keys=True)
    assert '"critical"' not in text
    assert "hidden_gold" not in text
    assert "target_state" not in text
    assert critical_id in text


def test_retry_success_keeps_result_when_remaining_repair_call_is_shadow_only():
    case = build_holdout_a_r1()[0]
    perfect = generate_candidate(case.task, 1.0, 991001)
    bad = generate_candidate(case.task, 0.0, 991002)
    executor = QueueModel("qwen3.5:9b-q8_0", {"executor": [_actions_json(perfect)]})
    repairer = QueueModel("cogito:3b-v1-preview-llama-q8_0", {"repairer": [_actions_json(bad)]})
    arm = _arms()[1]

    result = run_arm_task(
        case,
        arm,
        model_by_name={executor.model: executor, repairer.model: repairer},
        best_single_model=executor.model,
        repair_model=repairer.model,
        budget=PhysicalCallBudget(20),
        run_id="s1-r1-test",
    )

    assert result["seed_failure_verified"] is True
    assert result["success"] is True
    assert result["physical_calls_added"] == 2
    assert result["active_inference_calls"] == 1
    assert result["shadow_inference_calls"] == 1
    assert result["first_active_component"] == "retry"
    assert [row["component"] for row in result["raw_calls"]] == ["retry", "targeted_repair"]
    assert result["raw_calls"][0]["active_intervention"] is True
    assert result["raw_calls"][1]["shadow_only"] is True
    prompt_text = json.dumps([row["prompt"] for row in result["raw_calls"]], sort_keys=True)
    assert "hidden_gold" not in prompt_text
    assert "target_state" not in prompt_text


def test_active_repair_prompt_contains_only_public_requirement_metadata():
    case = next(case for case in build_holdout_a_r1() if any(req.critical for req in case.task.requirements))
    perfect = generate_candidate(case.task, 1.0, 991003)
    bad = generate_candidate(case.task, 0.0, 991004)
    executor = QueueModel("qwen3.5:9b-q8_0", {"executor": [_actions_json(perfect)]})
    repairer = QueueModel("cogito:3b-v1-preview-llama-q8_0", {"repairer": [_actions_json(bad)]})

    result = run_arm_task(
        case,
        _arms()[2],
        model_by_name={executor.model: executor, repairer.model: repairer},
        best_single_model=executor.model,
        repair_model=repairer.model,
        budget=PhysicalCallBudget(20),
        run_id="s1-r1-public-feedback",
    )

    repair_call = result["raw_calls"][0]
    assert repair_call["component"] == "targeted_repair"
    assert repair_call["active_intervention"] is True
    prompt_text = json.dumps(repair_call["prompt"], sort_keys=True)
    assert '"critical"' not in prompt_text
    assert "hidden_gold" not in prompt_text
    assert "target_state" not in prompt_text


def test_terminal_final_validator_turns_later_retry_into_shadow_and_cannot_be_overridden():
    case = build_holdout_a_r1()[0]
    perfect = generate_candidate(case.task, 1.0, 991005)
    bad = generate_candidate(case.task, 0.0, 991006)
    executor = QueueModel("qwen3.5:9b-q8_0", {"executor": [_actions_json(perfect)]})
    repairer = QueueModel("cogito:3b-v1-preview-llama-q8_0", {"repairer": [_actions_json(bad)]})
    arm = _arms()[2]

    result = run_arm_task(
        case,
        arm,
        model_by_name={executor.model: executor, repairer.model: repairer},
        best_single_model=executor.model,
        repair_model=repairer.model,
        budget=PhysicalCallBudget(20),
        run_id="s1-r1-test",
    )

    assert result["success"] is False
    assert result["physical_calls_added"] == 2
    assert result["active_inference_calls"] == 1
    assert result["shadow_inference_calls"] == 1
    assert result["first_active_component"] == "targeted_repair"
    assert result["raw_calls"][0]["active_intervention"] is True
    assert result["raw_calls"][1]["component"] == "retry"
    assert result["raw_calls"][1]["shadow_only"] is True


def _mock_models():
    best = MockModelAdapter("qwen3.5:9b-q8_0")
    repair = MockModelAdapter("cogito:3b-v1-preview-llama-q8_0")
    return best, repair


def test_full_r1_screen_consumes_exactly_80_calls_with_valid_exposure():
    best, repair = _mock_models()
    runtime = run_s1_screen(
        cases=build_holdout_a_r1(),
        arms=_arms(),
        model_by_name={best.model: best, repair.model: repair},
        best_single_model=best.model,
        repair_model=repair.model,
        run_id="s1-r1-full",
        exact_budget=80,
    )
    assert runtime["protocol_revision"] == "S1-R1"
    assert runtime["holdout"] == "A-R1"
    assert runtime["matched_task_limit"] == 10
    assert runtime["physical_model_calls"] == 80
    assert len(runtime["trials"]) == 40
    assert all(row["physical_calls_used"] == 20 for row in runtime["arm_accounting"])
    assert all(row["seed_failure_verified"] is True for row in runtime["trials"])
    assert all(int(row["active_inference_calls"]) >= 1 for row in runtime["trials"])
    assert all(int(row["active_inference_calls"]) + int(row["shadow_inference_calls"]) == 2 for row in runtime["trials"])
    assert not any(row.get("cache_hit") for row in runtime["model_calls"])
    first_ops = {
        row["first_active_component"]
        for row in runtime["trials"]
        if row["arm_id"] in {"S1-A1", "S1-A2", "S1-A3"}
    }
    assert {"retry", "targeted_repair"}.issubset(first_ops)


def test_full_r2_screen_consumes_exactly_200_calls_in_preregistered_balanced_order():
    best, repair = _mock_models()
    cases = build_holdout_a_r2()
    runtime = run_s1_screen(
        cases=cases,
        arms=_arms(50),
        model_by_name={best.model: best, repair.model: repair},
        best_single_model=best.model,
        repair_model=repair.model,
        run_id="s1-r2-full",
        exact_budget=200,
        protocol_revision="S1-R2",
    )
    assert runtime["protocol_revision"] == "S1-R2"
    assert runtime["holdout"] == "A-R2"
    assert runtime["matched_task_limit"] == 25
    assert runtime["physical_model_calls"] == 200
    assert len(runtime["trials"]) == 100
    assert all(row["physical_calls_used"] == 50 for row in runtime["arm_accounting"])
    assert all(row["physical_calls_added"] == 2 for row in runtime["trials"])
    assert all(row["seed_failure_verified"] is True for row in runtime["trials"])
    assert all(row["intervention_exposure_valid"] is True for row in runtime["trials"])
    assert not any(row.get("cache_hit") for row in runtime["model_calls"])

    expected_schedule = []
    for task_index, case in enumerate(cases):
        for arm_position, arm_id in enumerate(r2_arm_order(task_index)):
            expected_schedule.append({
                "task_index": task_index,
                "task_id": case.case_id,
                "arm_execution_position": arm_position,
                "arm_id": arm_id,
            })
    observed = [
        {key: row[key] for key in ("task_index", "task_id", "arm_execution_position", "arm_id")}
        for row in runtime["trials"]
    ]
    assert observed == expected_schedule


def test_r2_prompt_boundary_contains_no_hidden_or_fault_metadata():
    best, repair = _mock_models()
    runtime = run_s1_screen(
        cases=build_holdout_a_r2(),
        arms=_arms(50),
        model_by_name={best.model: best, repair.model: repair},
        best_single_model=best.model,
        repair_model=repair.model,
        run_id="s1-r2-prompt-boundary",
        exact_budget=200,
        protocol_revision="S1-R2",
    )
    text = json.dumps([row["prompt"] for row in runtime["model_calls"]], sort_keys=True)
    for forbidden in (
        '"critical"',
        "target_state",
        "hidden_gold",
        "injected_fault",
        "s1_r2_seed_failure",
        "stress_case",
    ):
        assert forbidden not in text


def test_r2_runtime_fails_closed_on_wrong_budget_or_per_arm_cap():
    best, repair = _mock_models()
    kwargs = dict(
        cases=build_holdout_a_r2(),
        model_by_name={best.model: best, repair.model: repair},
        best_single_model=best.model,
        repair_model=repair.model,
        run_id="s1-r2-invalid",
        protocol_revision="S1-R2",
    )
    with pytest.raises(ValueError, match="exact-200"):
        run_s1_screen(arms=_arms(50), exact_budget=199, **kwargs)
    with pytest.raises(ValueError, match="50 physical calls per arm"):
        run_s1_screen(arms=_arms(49), exact_budget=200, **kwargs)


def test_unknown_components_still_fail_closed():
    case = build_holdout_a_r1()[0]
    executor = QueueModel("qwen3.5:9b-q8_0", {"executor": []})
    repairer = QueueModel("cogito:3b-v1-preview-llama-q8_0", {"repairer": []})
    with pytest.raises(ValueError, match="unknown S1 component"):
        run_arm_task(
            case,
            {"arm_id": "bad", "role": "alternate_fixed_order", "order": "mystery_component", "physical_call_cap": 20},
            model_by_name={executor.model: executor, repairer.model: repairer},
            best_single_model=executor.model,
            repair_model=repairer.model,
            budget=PhysicalCallBudget(20),
            run_id="s1-r1-test",
        )
