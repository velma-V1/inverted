from inverted.arms import Arm
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, run_experiment


def test_runner_emits_stable_identifiers_and_all_arms():
    config = ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.8,), seeds=(1,), epochs=1,
        arms=tuple(a.value for a in Arm), max_candidates=2, max_tokens_per_trial=10000,
    )
    result = run_experiment(config, [MockModelAdapter(model="m", seed=1)], run_id="fixed-run")
    assert len(result.trials) == 6
    assert len({t.trial_id for t in result.trials}) == 6
    assert {t.arm for t in result.trials} == {a.value for a in Arm}
    assert result.run_id == "fixed-run"


def test_parser_failure_is_retained_as_failure():
    config = ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.8,), seeds=(1,), epochs=1,
        arms=(Arm.A_DIRECT.value,), max_candidates=1, max_tokens_per_trial=10000,
    )
    model = MockModelAdapter(model="broken", seed=1)
    model.malformed_roles = {"executor"}
    result = run_experiment(config, [model], run_id="r")
    trial = result.trials[0]
    assert trial.success is False
    assert "parser_failure" in trial.failure_reasons
    assert trial.model_calls[0].parse_success is False
