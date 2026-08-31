from collections import Counter

import inverted.runner as runner
import inverted.verdict as verdict
from inverted.arms import Arm
from inverted.models import MockModelAdapter


def _full_config():
    return runner.ExperimentConfig(
        families=("state", "policy", "reconciliation"),
        complexities=(1, 2, 3, 4),
        qualities=(0.20, 0.40, 0.60, 0.80, 0.95),
        seeds=(101, 211, 307, 401, 503),
        epochs=3,
        arms=tuple(a.value for a in Arm),
        decisive=True,
        minimum_primary_trials=180,
        sequential_seed_stages=(3, 4, 5),
        sequential_interim_confidence=(0.995, 0.99),
    )


def _models():
    return [
        MockModelAdapter(model="m1", seed=1),
        MockModelAdapter(model="m2", seed=2),
        MockModelAdapter(model="m3", seed=3),
    ]


def test_balanced_stages_preserve_full_6480_plan_and_all_models():
    assert hasattr(runner, "build_trial_stages"), "runner must expose build_trial_stages"
    stages = runner.build_trial_stages(_full_config(), _models())
    assert [len(stage) for stage in stages] == [3888, 1296, 1296]
    assert sum(map(len, stages)) == 6480

    dependent = {Arm.A_DIRECT.value, Arm.B_DIRECT_CHECKED.value, Arm.D_INVERTED.value}
    assert {item.model_index for item in stages[0] if item.arm in dependent} == {0, 1, 2}
    assert {item.seed for item in stages[0]} == {101, 211, 307}
    assert {item.seed for item in stages[1]} == {401}
    assert {item.seed for item in stages[2]} == {503}

    counts = Counter(item.arm for stage in stages for item in stage)
    assert counts == {
        Arm.A_DIRECT.value: 540,
        Arm.B_DIRECT_CHECKED.value: 540,
        Arm.C_SYSTEM.value: 900,
        Arm.D_INVERTED.value: 2700,
        Arm.E_RANDOM_AUDITOR.value: 900,
        Arm.F_ORACLE_AUDITOR.value: 900,
    }


def _support_summary():
    return {
        "by_arm": {
            "A_DIRECT": {"n": 100, "success_rate": 0.50, "catastrophic_rate": 0.01},
            "B_DIRECT_CHECKED": {"n": 100, "success_rate": 0.72, "catastrophic_rate": 0.01},
            "D_INVERTED": {"n": 500, "success_rate": 0.70, "catastrophic_rate": 0.005},
            "E_RANDOM_AUDITOR": {"n": 500, "success_rate": 0.60, "catastrophic_rate": 0.01},
        },
        "primary": {
            "d_minus_a": 0.20,
            "equal_budget_diff": 0.20,
            "d_minus_b": -0.02,
            "independent_task_clusters": 108,
        },
        "family_advantage": {"state": 0.20, "policy": 0.15, "reconciliation": 0.18},
        "model_advantage": {"m1": 0.20, "m2": 0.18, "m3": 0.16},
        "seed_advantage": {"101": 0.20, "211": 0.17, "307": 0.18},
    }


def test_interim_support_requires_high_confidence_and_unanimous_direction():
    assert hasattr(verdict, "decide_interim_stop"), "verdict must expose decide_interim_stop"
    cfg = _full_config()
    decision = verdict.decide_interim_stop(
        _support_summary(), cfg,
        stage_number=1,
        completed_seed_count=3,
        confidence=0.995,
        primary_interval={"estimate": 0.20, "lower": 0.11, "upper": 0.29},
    )
    assert decision["stop"] is True
    assert decision["verdict"] == "SUPPORTED"

    mixed = _support_summary()
    mixed["model_advantage"] = {"m1": 0.20, "m2": 0.18, "m3": -0.01}
    decision = verdict.decide_interim_stop(
        mixed, cfg,
        stage_number=1,
        completed_seed_count=3,
        confidence=0.995,
        primary_interval={"estimate": 0.20, "lower": 0.11, "upper": 0.29},
    )
    assert decision["stop"] is False


def test_interim_refutation_only_stops_when_high_confidence_rules_out_5pp_gain():
    assert hasattr(verdict, "decide_interim_stop"), "verdict must expose decide_interim_stop"
    cfg = _full_config()
    summary = _support_summary()
    summary["primary"]["d_minus_a"] = -0.01
    decision = verdict.decide_interim_stop(
        summary, cfg,
        stage_number=2,
        completed_seed_count=4,
        confidence=0.99,
        primary_interval={"estimate": -0.01, "lower": -0.07, "upper": 0.04},
    )
    assert decision["stop"] is True
    assert decision["verdict"] == "REFUTED"

    decision = verdict.decide_interim_stop(
        summary, cfg,
        stage_number=2,
        completed_seed_count=4,
        confidence=0.99,
        primary_interval={"estimate": -0.01, "lower": -0.08, "upper": 0.07},
    )
    assert decision["stop"] is False


def test_runner_can_stop_after_first_balanced_stage_without_losing_checkpointable_rows():
    assert hasattr(runner, "build_trial_stages"), "runner must expose build_trial_stages"
    cfg = runner.ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.8,),
        seeds=(1, 2, 3, 4, 5), epochs=1,
        arms=tuple(a.value for a in Arm),
        sequential_seed_stages=(3, 4, 5),
        sequential_interim_confidence=(0.995, 0.99),
    )
    model = MockModelAdapter(model="m", seed=1)

    def stop_after_stage_one(stage_number, completed_seed_count, total_seed_count, trials):
        if stage_number == 1:
            return {"stop": True, "verdict": "SUPPORTED", "reason": "test stop"}
        return {"stop": False}

    result = runner.run_experiment(cfg, [model], run_id="sequential-test", stage_callback=stop_after_stage_one)
    assert len(result.trials) == 18
    assert result.stopped_early is True
    assert result.completed_seed_count == 3
    assert result.sequential_decision["verdict"] == "SUPPORTED"
