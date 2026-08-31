from inverted.arms import Arm
from inverted.checkpoint import CheckpointStore
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, build_trial_plan, run_experiment


def small_config():
    return ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.2, 0.8), seeds=(1, 2), epochs=1,
        arms=tuple(a.value for a in Arm), max_candidates=2, max_tokens_per_trial=10000,
        bootstrap_samples=50,
    )


def test_checkpoint_round_trips_full_trial_records(tmp_path):
    cfg = small_config()
    model = MockModelAdapter(model="m", seed=3, executor_accuracy=0.6, auditor_accuracy=0.9)
    result = run_experiment(cfg, [model], run_id="checkpoint-source")
    store = CheckpointStore(tmp_path / "checkpoint.jsonl")

    store.append_trial(result.trials[0])
    loaded = store.load_trials()

    assert len(loaded) == 1
    assert loaded[0].to_dict(include_calls=True) == result.trials[0].to_dict(include_calls=True)


def test_resume_skips_checkpointed_work_and_reconstructs_complete_result(tmp_path):
    cfg = small_config()
    model = MockModelAdapter(model="m", seed=3, executor_accuracy=0.6, auditor_accuracy=0.9)
    uninterrupted = run_experiment(cfg, [model], run_id="resume-run")
    store = CheckpointStore(tmp_path / "checkpoint.jsonl")
    for trial in uninterrupted.trials[:5]:
        store.append_trial(trial)

    resumed = run_experiment(
        cfg,
        [MockModelAdapter(model="m", seed=3, executor_accuracy=0.6, auditor_accuracy=0.9)],
        run_id="resume-run",
        checkpoint_store=store,
        resume=True,
    )

    assert len(resumed.trials) == len(build_trial_plan(cfg, [model]))
    assert len({t.trial_id for t in resumed.trials}) == len(resumed.trials)
    assert sorted((t.trial_id, t.success, t.terminal_status) for t in resumed.trials) == sorted(
        (t.trial_id, t.success, t.terminal_status) for t in uninterrupted.trials
    )
    assert len(store.load_trials()) == len(resumed.trials)


def test_progress_reports_exact_deduplicated_plan_total(tmp_path):
    cfg = small_config()
    model = MockModelAdapter(model="m", seed=3)
    seen = []

    result = run_experiment(
        cfg,
        [model],
        run_id="progress-run",
        checkpoint_store=CheckpointStore(tmp_path / "progress.jsonl"),
        progress_callback=lambda completed, total, item: seen.append((completed, total, item.arm)),
    )

    expected = len(build_trial_plan(cfg, [model]))
    assert len(result.trials) == expected
    assert len(seen) == expected
    assert seen[0][0] == 1
    assert seen[-1][0] == expected
    assert all(total == expected for _, total, _ in seen)
