from __future__ import annotations

from dataclasses import asdict
import importlib
import json
from typing import Any

import pytest

from inverted.domain import Action, Candidate
from inverted.models import MockModelAdapter
from inverted.oracle import apply_actions, evaluate_task
from inverted.test2_cases import build_execution_cases, build_formalization_cases, build_holdout_cases
import inverted.test3_s1_cases as s1_cases


R3_PROTOCOL = "S1-R3"
R3_HOLDOUT = "A-R3"
R3_SEED_BASE = 811000
R3_SEED_STRIDE = 233


class CountingMockModelAdapter(MockModelAdapter):
    def __init__(self, model: str):
        super().__init__(model)
        self.call_count = 0

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]):
        self.call_count += 1
        return super().complete(messages, role=role, context=context)


def _runtime():
    return importlib.import_module("inverted.test3_s1_r3_runtime")


def _r3_arms(cap: int = 50):
    return [
        {"arm_id": "S1-A0", "role": "best_single_model_baseline", "order": None, "physical_call_cap": cap},
        {"arm_id": "S1-A1", "role": "current_best_fixed_hybrid", "order": "requirement_validator -> retry -> targeted_repair -> final_validator", "physical_call_cap": cap},
        {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "requirement_validator -> targeted_repair -> final_validator -> retry", "physical_call_cap": cap},
        {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "requirement_validator -> targeted_repair -> retry -> final_validator", "physical_call_cap": cap},
    ]


def _legacy_colliding_arms(cap: int = 50):
    arms = _r3_arms(cap)
    arms[-1] = {
        "arm_id": "S1-A3",
        "role": "random_order_negative_control",
        "order": "retry -> targeted_repair -> final_validator -> requirement_validator",
        "physical_call_cap": cap,
    }
    return arms


def _mock_models():
    best = CountingMockModelAdapter("qwen3.5:9b-q8_0")
    repair = CountingMockModelAdapter("cogito:3b-v1-preview-llama-q8_0")
    return best, repair


def test_r3_holdout_is_fresh_exact_25_and_disjoint_from_all_prior_namespaces():
    cases = s1_cases.build_holdout_a_r3()
    assert len(cases) == 25
    expected = []
    for level in (1, 2, 3, 4):
        expected.extend((family, level) for family in (
            "state", "policy", "reconciliation", "preservation", "dependency_order", "repair_containment"
        ))
    expected.append(("repair_containment", 4))
    assert [(case.task.family, case.task.complexity) for case in cases] == expected
    assert [case.task.metadata["seed"] for case in cases] == [R3_SEED_BASE + i * R3_SEED_STRIDE for i in range(25)]
    assert all(case.case_id.startswith("test3-s1-AR3-") for case in cases)
    assert "stress" in cases[-1].case_id

    prior_seeds = {case.task.metadata["seed"] for case in build_holdout_cases()}
    prior_seeds.update(case.task.metadata["seed"] for case in build_execution_cases())
    prior_seeds.update(case.task.metadata["seed"] for case in build_formalization_cases())
    prior_seeds.update(case.task.metadata["seed"] for case in s1_cases.build_holdout_a())
    prior_seeds.update(case.task.metadata["seed"] for case in s1_cases.build_holdout_a_r1())
    prior_seeds.update(case.task.metadata["seed"] for case in s1_cases.build_holdout_a_r2())
    assert not prior_seeds.intersection(case.task.metadata["seed"] for case in cases)


def test_r3_seed_failures_are_deterministic_verified_bad_and_task_immutable():
    for case in s1_cases.build_holdout_a_r3():
        before = asdict(case.task)
        first = s1_cases.build_seed_failure_r3(case)
        second = s1_cases.build_seed_failure_r3(case)
        assert asdict(first) == asdict(second)
        assert evaluate_task(case.task, first.state, first.actions).success is False
        assert first.metadata.get("s1_r3_seed_failure") is True
        assert asdict(case.task) == before


def test_r3_causal_signatures_detect_r2_control_collision_and_keep_r3_fixed_arms_distinct():
    signature = _runtime().causal_order_signature
    legacy = _legacy_colliding_arms()
    assert signature(legacy[1]) == signature(legacy[3])

    observed = [signature(arm) for arm in _r3_arms()[1:]]
    assert len(set(observed)) == 3
    assert observed == [
        ("retry", "targeted_repair", "final_validator"),
        ("targeted_repair", "final_validator", "retry"),
        ("targeted_repair", "retry", "final_validator"),
    ]


def test_r3_runtime_fails_closed_before_inference_when_causal_orders_collide():
    runtime = _runtime()
    best, repair = _mock_models()
    with pytest.raises(ValueError, match="causal-order collision"):
        runtime.run_s1_r3_screen(
            cases=s1_cases.build_holdout_a_r3(),
            arms=_legacy_colliding_arms(),
            model_by_name={best.model: best, repair.model: repair},
            best_single_model=best.model,
            repair_model=repair.model,
            run_id="s1-r3-collision",
            exact_budget=200,
        )
    assert best.call_count == 0
    assert repair.call_count == 0


def test_r3_repair_patch_composition_preserves_unrelated_correct_work_and_replaces_failed_path():
    runtime = _runtime()
    case = next(row for row in s1_cases.build_holdout_a_r3() if row.task.family == "repair_containment" and row.task.complexity >= 2)
    previous = s1_cases.build_seed_failure_r3(case)
    status = evaluate_task(case.task, previous.state, previous.actions)
    failed_id = status.failed_requirement_ids[0]
    failed_req = next(req for req in case.task.requirements if req.id == failed_id)
    unrelated = next(action for action in previous.actions if action.path != failed_req.path)
    patch = (Action(str(failed_req.metadata.get("op", "set")), failed_req.path, failed_req.expected),)

    composed = runtime.compose_repair_patch(
        case.task, previous, patch, list(status.failed_requirement_ids), "r3-composed"
    )
    assert unrelated in composed.actions
    assert sum(action.path == failed_req.path for action in composed.actions) == 1
    assert evaluate_task(case.task, composed.state, composed.actions).success is True


def test_r3_patch_composition_removes_failed_action_absent_operation_even_with_empty_patch():
    runtime = _runtime()
    case = next(row for row in s1_cases.build_holdout_a_r3() if row.task.family == "policy" and any(req.kind == "action_absent" for req in row.task.requirements))
    forbidden = next(req for req in case.task.requirements if req.kind == "action_absent")
    actions = (Action(forbidden.path, "junk.path", True),)
    previous = Candidate("forbidden", apply_actions(case.task.initial_state, actions), actions)
    status = evaluate_task(case.task, previous.state, previous.actions)
    assert forbidden.id in status.failed_requirement_ids

    composed = runtime.compose_repair_patch(case.task, previous, (), [forbidden.id], "r3-remove-forbidden")
    assert all(action.op != forbidden.path for action in composed.actions)


def test_r3_action_before_patch_replaces_old_pair_and_preserves_patch_order():
    runtime = _runtime()
    case = next(row for row in s1_cases.build_holdout_a_r3() if row.task.family == "dependency_order")
    previous = s1_cases.build_seed_failure_r3(case)
    order_req = next(req for req in case.task.requirements if req.kind == "action_before")
    status = evaluate_task(case.task, previous.state, previous.actions)
    assert order_req.id in status.failed_requirement_ids
    patch = (
        Action(**dict(order_req.metadata.get("before_action") or {})),
        Action(**dict(order_req.metadata.get("after_action") or {})),
    )

    composed = runtime.compose_repair_patch(case.task, previous, patch, [order_req.id], "r3-order-repair")
    ops = [action.op for action in composed.actions]
    assert ops.index(str(order_req.path)) < ops.index(str(order_req.expected))
    assert evaluate_task(case.task, composed.state, composed.actions).success is True


def test_full_r3_mock_screen_is_exact_200_and_exposure_valid_with_distinct_control():
    runtime_mod = _runtime()
    best, repair = _mock_models()
    runtime = runtime_mod.run_s1_r3_screen(
        cases=s1_cases.build_holdout_a_r3(),
        arms=_r3_arms(),
        model_by_name={best.model: best, repair.model: repair},
        best_single_model=best.model,
        repair_model=repair.model,
        run_id="s1-r3-full",
        exact_budget=200,
    )
    assert runtime["protocol_revision"] == R3_PROTOCOL
    assert runtime["holdout"] == R3_HOLDOUT
    assert runtime["matched_task_limit"] == 25
    assert runtime["physical_model_calls"] == 200
    assert len(runtime["trials"]) == 100
    assert runtime["protocol_valid_for_primary_claim"] is True
    assert all(row["physical_calls_added"] == 2 for row in runtime["trials"])
    assert all(row["seed_failure_verified"] is True for row in runtime["trials"])
    assert all(row["intervention_exposure_valid"] is True for row in runtime["trials"])
    assert not any(row.get("cache_hit") for row in runtime["model_calls"])

    expected_schedule = []
    for task_index, case in enumerate(s1_cases.build_holdout_a_r3()):
        for arm_position, arm_id in enumerate(s1_cases.r3_arm_order(task_index)):
            expected_schedule.append((task_index, case.case_id, arm_position, arm_id))
    observed = [
        (row["task_index"], row["task_id"], row["arm_execution_position"], row["arm_id"])
        for row in runtime["trials"]
    ]
    assert observed == expected_schedule
    assert runtime["intervention_exposure"]["causal_order_signatures_unique"] is True


def test_r3_repair_prompt_explicitly_declares_patch_composition_and_keeps_public_boundary():
    runtime_mod = _runtime()
    best, repair = _mock_models()
    runtime = runtime_mod.run_s1_r3_screen(
        cases=s1_cases.build_holdout_a_r3(),
        arms=_r3_arms(),
        model_by_name={best.model: best, repair.model: repair},
        best_single_model=best.model,
        repair_model=repair.model,
        run_id="s1-r3-prompt",
        exact_budget=200,
    )
    repair_prompts = [row["prompt"] for row in runtime["model_calls"] if row["component"] == "targeted_repair"]
    text = json.dumps(repair_prompts, sort_keys=True).lower()
    assert "repair patch" in text
    assert "composes this patch with previous_actions" in text
    for forbidden in (
        '"critical"', "target_state", "hidden_gold", "injected_fault",
        "s1_r1_seed_failure", "s1_r2_seed_failure", "s1_r3_seed_failure", "stress_case",
    ):
        assert forbidden not in text
