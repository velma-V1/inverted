from collections import Counter

from inverted.arms import Arm, Budget, run_arm
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, build_trial_plan
from inverted.tasks import generate_task


def test_execution_plan_removes_quality_and_model_redundancy():
    config = ExperimentConfig(
        families=("state",),
        complexities=(1,),
        qualities=(0.2, 0.8),
        seeds=(1,),
        epochs=1,
        arms=tuple(a.value for a in Arm),
    )
    models = [MockModelAdapter(model="m1", seed=1), MockModelAdapter(model="m2", seed=2)]

    plan = build_trial_plan(config, models)
    counts = Counter(item.arm for item in plan)

    assert counts == {
        Arm.A_DIRECT.value: 2,
        Arm.B_DIRECT_CHECKED.value: 2,
        Arm.C_SYSTEM.value: 2,
        Arm.D_INVERTED.value: 4,
        Arm.E_RANDOM_AUDITOR.value: 2,
        Arm.F_ORACLE_AUDITOR.value: 2,
    }
    assert len(plan) == 14


def test_decisive_three_model_plan_is_exactly_6480_trial_units():
    config = ExperimentConfig(
        families=("state", "policy", "reconciliation"),
        complexities=(1, 2, 3, 4),
        qualities=(0.20, 0.40, 0.60, 0.80, 0.95),
        seeds=(101, 211, 307, 401, 503),
        epochs=3,
        arms=tuple(a.value for a in Arm),
        decisive=True,
        minimum_primary_trials=180,
    )
    models = [
        MockModelAdapter(model="family-a", seed=1),
        MockModelAdapter(model="family-b", seed=2),
        MockModelAdapter(model="family-c", seed=3),
    ]

    plan = build_trial_plan(config, models)
    counts = Counter(item.arm for item in plan)

    assert len(plan) == 6480
    assert counts == {
        Arm.A_DIRECT.value: 540,
        Arm.B_DIRECT_CHECKED.value: 540,
        Arm.C_SYSTEM.value: 900,
        Arm.D_INVERTED.value: 2700,
        Arm.E_RANDOM_AUDITOR.value: 900,
        Arm.F_ORACLE_AUDITOR.value: 900,
    }


def test_non_ai_candidate_sequence_is_invariant_to_model_identity():
    task = generate_task("policy", 4, 73)
    budget = Budget(max_candidates=3, max_tokens=10000)
    m1 = MockModelAdapter(model="auditor-one", seed=1)
    m2 = MockModelAdapter(model="auditor-two", seed=1)

    a = run_arm(Arm.F_ORACLE_AUDITOR, task, m1, 0.0, 41, "same-run", budget, epoch=2)
    b = run_arm(Arm.F_ORACLE_AUDITOR, task, m2, 0.0, 41, "same-run", budget, epoch=2)

    def evidence(trial):
        return [
            {
                "actions": event["actions"],
                "post_state": event["post_state"],
                "faults": event["faults"],
                "oracle_success": event["oracle_success"],
            }
            for event in trial.candidate_events
        ]

    assert evidence(a) == evidence(b)
