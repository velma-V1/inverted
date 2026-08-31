from pathlib import Path

import pytest

import inverted.cli as cli
from inverted.arms import Arm
from inverted.checkpoint import CheckpointStore
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, build_trial_plan, build_trial_stages, run_experiment, trial_record_key


def _full_config():
    return ExperimentConfig(
        families=("state", "policy", "reconciliation"),
        complexities=(1, 2, 3, 4),
        qualities=(0.20, 0.40, 0.60, 0.80, 0.95),
        seeds=(101, 211, 307, 401, 503),
        epochs=3,
        arms=tuple(a.value for a in Arm),
        decisive=True,
        minimum_primary_trials=180,
        value_checkpoint_seed_stages=(1, 2),
        sequential_seed_stages=(3, 4, 5),
        sequential_interim_confidence=(0.995, 0.99),
    )


def _models():
    return [
        MockModelAdapter(model="m1", seed=1),
        MockModelAdapter(model="m2", seed=2),
        MockModelAdapter(model="m3", seed=3),
    ]


def test_20_40_value_checkpoints_are_balanced_without_changing_full_6480_plan():
    stages = build_trial_stages(_full_config(), _models())

    assert [len(stage) for stage in stages] == [1296, 1296, 1296, 1296, 1296]
    assert sum(map(len, stages)) == 6480
    assert [{item.seed for item in stage} for stage in stages] == [
        {101}, {211}, {307}, {401}, {503}
    ]

    dependent = {Arm.A_DIRECT.value, Arm.B_DIRECT_CHECKED.value, Arm.D_INVERTED.value}
    for stage in stages:
        assert {item.model_index for item in stage if item.arm in dependent} == {0, 1, 2}


def test_value_checkpoint_snapshot_is_durable_and_explicitly_non_decisive(tmp_path):
    assert hasattr(cli, "_persist_value_checkpoint")
    summary = {
        "n_trials": 1296,
        "by_arm": {
            "A_DIRECT": {"success_rate": 0.50, "catastrophic_rate": 0.02},
            "B_DIRECT_CHECKED": {"success_rate": 0.72, "catastrophic_rate": 0.01},
            "D_INVERTED": {"success_rate": 0.68, "catastrophic_rate": 0.01},
            "E_RANDOM_AUDITOR": {"success_rate": 0.55, "catastrophic_rate": 0.02},
        },
        "primary": {
            "d_minus_a": 0.18,
            "d_minus_b": -0.04,
            "equal_budget_diff": 0.18,
            "ci95": {"lower": 0.05, "upper": 0.30},
            "independent_task_clusters": 36,
        },
        "family_advantage": {"state": 0.20, "policy": 0.16, "reconciliation": 0.18},
        "model_advantage": {"m1": 0.20, "m2": 0.18, "m3": 0.16},
        "seed_advantage": {"101": 0.18},
        "complexity_advantage": {"1": 0.20, "2": 0.18, "3": 0.16, "4": 0.18},
        "quality_crossover": {"crossover_quality": 0.6, "points": []},
    }

    paths = cli._persist_value_checkpoint(tmp_path, "run-x", 1, 5, summary)

    payload = __import__("json").loads(Path(paths["json"]).read_text(encoding="utf-8"))
    text = Path(paths["text"]).read_text(encoding="utf-8")
    assert payload["status"] == "EXPLORATORY_NON_DECISIVE"
    assert payload["completed_seed_count"] == 1
    assert payload["percent"] == 20.0
    assert payload["metrics"]["d_minus_a"] == 0.18
    assert payload["metrics"]["d_minus_b"] == -0.04
    assert payload["metrics"]["d_minus_e"] == pytest.approx(0.13)
    assert "NOT A SCIENTIFIC VERDICT" in text
    assert "D - A" in text


def test_mid_stage_manual_stop_can_resume_same_checkpoint_without_duplicate_trials(tmp_path):
    cfg = ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.8,),
        seeds=(1, 2, 3, 4, 5), epochs=1,
        arms=tuple(a.value for a in Arm),
        value_checkpoint_seed_stages=(1, 2),
    )
    checkpoint = CheckpointStore(tmp_path / "resume.checkpoint.jsonl")

    class ManualStop(RuntimeError):
        pass

    def interrupt(completed, total, item):
        if completed == 7:
            raise ManualStop("simulated manual stop")

    with pytest.raises(ManualStop):
        run_experiment(
            cfg, [MockModelAdapter(model="resume-model", seed=7)],
            run_id="resume-run", checkpoint_store=checkpoint, resume=True,
            progress_callback=interrupt,
        )

    assert len(checkpoint.load_trials()) == 7

    result = run_experiment(
        cfg, [MockModelAdapter(model="resume-model", seed=7)],
        run_id="resume-run", checkpoint_store=checkpoint, resume=True,
    )
    expected = len(build_trial_plan(cfg, [MockModelAdapter(model="resume-model", seed=7)]))
    rows = checkpoint.load_trials()
    assert len(result.trials) == expected
    assert len(rows) == expected
    assert len({trial_record_key(row) for row in rows}) == expected


def test_checkpoint_publisher_copies_value_snapshots_to_remote_results():
    text = Path("scripts/publish-inverted-checkpoints.ps1").read_text(encoding="utf-8")
    assert "value-checkpoints" in text
    assert "value-checkpoint-" in text
