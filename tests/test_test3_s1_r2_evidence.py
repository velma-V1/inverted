from inverted.models import MockModelAdapter
from inverted.test2_types import PhysicalCallBudget
from inverted.test3_s1_cases import build_holdout_a_r2
from inverted.test3_s1_runtime import run_arm_task


def test_r2_trial_records_public_requirement_kind_map_for_category_forensics():
    case = next(row for row in build_holdout_a_r2() if row.task.family == "repair_containment")
    executor = MockModelAdapter("qwen3.5:9b-q8_0")
    repairer = MockModelAdapter("cogito:3b-v1-preview-llama-q8_0")
    arm = {
        "arm_id": "S1-A2",
        "role": "alternate_fixed_order",
        "order": "requirement_validator -> targeted_repair -> final_validator -> retry",
        "physical_call_cap": 50,
    }
    result = run_arm_task(
        case,
        arm,
        model_by_name={executor.model: executor, repairer.model: repairer},
        best_single_model=executor.model,
        repair_model=repairer.model,
        budget=PhysicalCallBudget(50),
        run_id="s1-r2-evidence-test",
        protocol_revision="S1-R2",
    )
    expected = {row["id"]: row["kind"] for row in case.task.metadata["public_requirements"]}
    assert result["requirement_kinds"] == expected
    assert "critical" not in result["requirement_kinds"]
    assert set(result["seed_passed_requirements"]) | set(result["seed_failed_requirements"]) == set(expected)
