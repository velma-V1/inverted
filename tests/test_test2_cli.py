from pathlib import Path

from inverted.test2_cli import load_test2_config, main
from inverted.test2_local import LOCAL_MODELS


def test_local_config_has_exact_models_and_hard_480_call_limit():
    cfg = load_test2_config(Path("configs/test2-local.yaml"))
    assert tuple(cfg["local"]["models"]) == LOCAL_MODELS
    assert cfg["local"]["hard_call_limit"] == 480
    assert cfg["local"]["early_stop"] is False


def test_local_dry_plan_prints_full_phase_budget_without_running_models(capsys):
    rc = main(["local", "--config", "configs/test2-local.yaml", "--dry-plan"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PLANNED_MAX_PHYSICAL_CALLS=480" in out
    for model in LOCAL_MODELS:
        assert model in out


def test_model_free_smoke_writes_complete_evidence(tmp_path):
    rc = main([
        "model-free",
        "--config", "configs/test2-model-free.yaml",
        "--output-dir", str(tmp_path),
        "--run-id", "ci-test2-smoke",
        "--seed-count", "1",
    ])
    assert rc == 0
    run_dir = tmp_path / "ci-test2-smoke"
    required = [
        "TEST2-COMPLETE-EVIDENCE.txt",
        "TEST2-NEXT-STRIDE-REPORT.txt",
        "effects/failure-kill-matrix.csv",
        "effects/failure-recovery-matrix.csv",
        "effects/component-slice-effects.csv",
        "order/every-valid-order.csv",
        "order/order-ranking.csv",
        "order/order-slice-ranking.csv",
        "order/candidate-saturation.csv",
        "order/candidate-independence.json",
        "order/candidate-independence-strata.csv",
        "order/retry-repair-thresholds.csv",
        "raw/every-trial.jsonl",
        "raw/every-candidate.jsonl",
        "raw/every-event.jsonl",
    ]
    for relative in required:
        assert (run_dir / relative).exists(), relative

    assert (run_dir / "raw/every-trial.jsonl").stat().st_size > 0
    assert (run_dir / "raw/every-candidate.jsonl").stat().st_size > 0
    assert (run_dir / "raw/every-event.jsonl").stat().st_size > 0
