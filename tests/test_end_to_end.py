from inverted.arms import Arm
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, run_experiment
from inverted.statistics import aggregate_trials
from inverted.verdict import decide_verdict


def verdict_for(executor_accuracy, auditor_accuracy, *, run_id, complexities=(1,2), qualities=(0.8,0.95), seeds=tuple(range(1,9))):
    cfg = ExperimentConfig(
        families=("state","policy","reconciliation"), complexities=complexities, qualities=qualities,
        seeds=seeds, epochs=1, arms=tuple(a.value for a in Arm), max_candidates=3,
        max_tokens_per_trial=10000, decisive=True, minimum_primary_trials=10,
        bootstrap_samples=500, bootstrap_seed=1,
    )
    result = run_experiment(cfg, [MockModelAdapter(model="controlled", seed=7, executor_accuracy=executor_accuracy, auditor_accuracy=auditor_accuracy)], run_id=run_id)
    summary = aggregate_trials(result.trials, cfg.bootstrap_samples, cfg.bootstrap_seed)
    return decide_verdict(summary, cfg), summary


def test_end_to_end_supported_path():
    verdict, summary = verdict_for(0.2, 1.0, run_id="e2e-supported")
    assert verdict["verdict"] == "SUPPORTED"
    assert summary["primary"]["d_minus_a"] >= 0.10
    assert summary["primary"]["ci95"]["lower"] > 0


def test_end_to_end_refuted_path():
    verdict, summary = verdict_for(1.0, 0.0, run_id="e2e-refuted")
    assert verdict["verdict"] == "REFUTED"
    assert summary["primary"]["d_minus_a"] < 0


def test_end_to_end_intermediate_mock_does_not_false_support():
    # This scenario is intentionally near the boundary. Its exact REFUTED vs
    # INCONCLUSIVE class can change when legitimate RNG/pairing internals change,
    # so the end-to-end invariant is that it must never manufacture SUPPORT.
    # The exact INCONCLUSIVE branch is covered deterministically in test_verdict.py.
    verdict, _ = verdict_for(
        0.75, 0.80, run_id="e2e-intermediate", complexities=(1,), qualities=(0.6,0.8), seeds=tuple(range(1,13))
    )
    assert verdict["verdict"] in {"REFUTED", "INCONCLUSIVE"}
