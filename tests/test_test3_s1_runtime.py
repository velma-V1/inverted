from __future__ import annotations

import json

import pytest

from inverted.models import MockModelAdapter
from inverted.system_executor import generate_candidate
from inverted.test2_types import PhysicalCallBudget
from inverted.test3_s1_cases import build_holdout_a
from inverted.test3_s1_runtime import (
    matched_task_limit,
    run_arm_task,
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


def test_worst_case_budget_and_matched_prefix_are_frozen_by_order_not_outcome():
    arms = [
        {"arm_id": "S1-A0", "role": "best_single_model_baseline", "order": None, "physical_call_cap": 20},
        {"arm_id": "S1-A1", "role": "current_best_fixed_hybrid", "order": "requirement_validator -> retry -> targeted_repair -> final_validator", "physical_call_cap": 20},
        {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "retry -> requirement_validator -> targeted_repair -> final_validator", "physical_call_cap": 20},
        {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "targeted_repair -> retry -> requirement_validator -> final_validator", "physical_call_cap": 20},
    ]
    assert worst_case_calls_for_arm(arms[0]) == 1
    assert worst_case_calls_for_arm(arms[1]) == 3
    assert matched_task_limit(arms, available_cases=12) == 6


def test_order_runtime_retries_after_validator_block_and_never_exposes_hidden_gold_to_prompts():
    case = build_holdout_a()[0]
    perfect = generate_candidate(case.task, 1.0, 991001)
    executor = QueueModel("qwen3.5:9b-q8_0", {
        "executor": ['{"actions":[]}', _actions_json(perfect)],
    })
    repairer = QueueModel("llama3.1:8b", {"repairer": [_actions_json(perfect)]})
    arm = {
        "arm_id": "S1-A1",
        "role": "current_best_fixed_hybrid",
        "order": "requirement_validator -> retry -> final_validator",
        "physical_call_cap": 20,
    }
    result = run_arm_task(
        case,
        arm,
        model_by_name={executor.model: executor, repairer.model: repairer},
        best_single_model=executor.model,
        repair_model=repairer.model,
        budget=PhysicalCallBudget(20),
        run_id="s1-test",
    )
    assert result["success"] is True
    assert result["physical_calls_added"] == 2
    assert [row["component"] for row in result["trace"]] == [
        "initial_executor", "requirement_validator", "retry", "final_validator"
    ]
    prompt_text = json.dumps([row["prompt"] for row in result["raw_calls"]], sort_keys=True)
    assert "hidden_gold" not in prompt_text
    assert "target_state" not in prompt_text


def test_final_validator_is_terminal_and_unknown_components_fail_closed():
    case = build_holdout_a()[0]
    perfect = generate_candidate(case.task, 1.0, 991002)
    executor = QueueModel("qwen3.5:9b-q8_0", {"executor": ['{"actions":[]}', _actions_json(perfect)]})
    repairer = QueueModel("llama3.1:8b", {"repairer": [_actions_json(perfect)]})
    base = dict(
        model_by_name={executor.model: executor, repairer.model: repairer},
        best_single_model=executor.model,
        repair_model=repairer.model,
        run_id="s1-test",
    )
    terminal = run_arm_task(
        case,
        {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "final_validator -> retry -> targeted_repair", "physical_call_cap": 20},
        budget=PhysicalCallBudget(20),
        **base,
    )
    assert terminal["success"] is False
    assert terminal["physical_calls_added"] == 1
    assert [row["component"] for row in terminal["trace"]] == ["initial_executor", "final_validator"]

    with pytest.raises(ValueError, match="unknown S1 component"):
        run_arm_task(
            case,
            {"arm_id": "bad", "role": "alternate_fixed_order", "order": "mystery_component", "physical_call_cap": 20},
            budget=PhysicalCallBudget(20),
            **base,
        )
