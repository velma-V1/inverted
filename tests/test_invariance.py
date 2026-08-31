import json

from inverted.arms import Arm, Budget, run_arm
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, run_experiment
from inverted.statistics import aggregate_trials
from inverted.tasks import generate_task


def _cfg(arms):
    return ExperimentConfig(
        families=("state", "policy"), complexities=(1, 2), qualities=(0.2, 0.8),
        seeds=(1, 2, 3), epochs=1, arms=tuple(arms), max_candidates=3,
        max_tokens_per_trial=10000, decisive=False, bootstrap_samples=200, bootstrap_seed=9,
    )


def _normalized_outcomes(result):
    rows = []
    for t in result.trials:
        model = t.model if t.arm in {"A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED"} else "CONTROL"
        rows.append((
            t.task_id, t.arm, model, t.epoch, t.seed, t.configured_executor_quality,
            t.success, t.terminal_status, t.requirement_accuracy, t.catastrophic,
            t.candidate_attempts, t.rejections,
        ))
    return sorted(rows, key=str)


def test_model_order_does_not_change_experimental_outcomes():
    models_a = [
        MockModelAdapter(model="m1", seed=11, executor_accuracy=0.45, auditor_accuracy=0.90),
        MockModelAdapter(model="m2", seed=22, executor_accuracy=0.75, auditor_accuracy=0.80),
    ]
    models_b = list(reversed([
        MockModelAdapter(model="m1", seed=11, executor_accuracy=0.45, auditor_accuracy=0.90),
        MockModelAdapter(model="m2", seed=22, executor_accuracy=0.75, auditor_accuracy=0.80),
    ]))
    cfg = _cfg(a.value for a in Arm)

    first = run_experiment(cfg, models_a, run_id="model-order")
    second = run_experiment(cfg, models_b, run_id="model-order")

    assert _normalized_outcomes(first) == _normalized_outcomes(second)
    assert aggregate_trials(first.trials, 200, 9)["primary"] == aggregate_trials(second.trials, 200, 9)["primary"]


def test_arm_order_does_not_change_experimental_outcomes():
    models = [MockModelAdapter(model="m", seed=31, executor_accuracy=0.55, auditor_accuracy=0.85)]
    arms = [a.value for a in Arm]

    first = run_experiment(_cfg(arms), models, run_id="arm-order")
    second = run_experiment(_cfg(reversed(arms)), [MockModelAdapter(model="m", seed=31, executor_accuracy=0.55, auditor_accuracy=0.85)], run_id="arm-order")

    assert _normalized_outcomes(first) == _normalized_outcomes(second)
    assert aggregate_trials(first.trials, 200, 9)["primary"] == aggregate_trials(second.trials, 200, 9)["primary"]


def test_malformed_executor_is_recorded_as_parser_failure():
    task = generate_task("state", 2, 51)
    model = MockModelAdapter(model="malformed-exec", seed=1)
    model.malformed_roles.add("executor")

    trial = run_arm(Arm.A_DIRECT, task, model, 0.8, 7, "malformed", Budget(max_candidates=3, max_tokens=10000))

    assert trial.success is False
    assert "parser_failure" in trial.failure_reasons
    assert trial.model_calls[0].parse_success is False
    assert trial.model_calls[0].parse_error


def test_malformed_auditor_rejects_candidates_and_records_parser_failures():
    task = generate_task("policy", 2, 52)
    model = MockModelAdapter(model="malformed-audit", seed=1)
    model.malformed_roles.add("auditor")

    trial = run_arm(Arm.D_INVERTED, task, model, 0.8, 7, "malformed", Budget(max_candidates=3, max_tokens=10000))

    assert trial.success is False
    assert trial.rejections == trial.candidate_attempts == 3
    assert "parser_failure" in trial.failure_reasons
    assert all(call.parse_success is False for call in trial.model_calls)
    assert all(event["decision"] == "error" for event in trial.candidate_events)
