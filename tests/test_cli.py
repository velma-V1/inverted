import json
from pathlib import Path
import yaml
import pytest
from inverted.cli import load_config, main


def test_cli_runs_offline_smoke_and_writes_all_artifacts(tmp_path, capsys):
    cfg = {
        "benchmark": {
            "families": ["state"], "complexities": [1], "qualities": [0.8], "seeds": [1], "epochs": 1,
            "arms": ["A_DIRECT","B_DIRECT_CHECKED","C_SYSTEM","D_INVERTED","E_RANDOM_AUDITOR","F_ORACLE_AUDITOR"],
            "max_candidates": 2, "max_tokens_per_trial": 10000, "decisive": False,
            "minimum_primary_trials": 20, "bootstrap_samples": 50, "bootstrap_seed": 1
        },
        "models": [{"provider":"mock","model":"mock-ci","seed":1,"executor_accuracy":0.6,"auditor_accuracy":0.9}],
        "report": {"include_raw_rows": True, "capture_content": True}
    }
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(cfg))
    out = tmp_path / "runs"
    code = main(["--config", str(path), "--output-dir", str(out), "--run-id", "cli-smoke"])
    assert code == 0
    run = out / "cli-smoke"
    assert (run / "report.txt").exists()
    assert json.loads((run / "summary.json").read_text())["verdict"]["verdict"] == "NON-DECISIVE"
    printed = capsys.readouterr().out
    assert "FULL MODEL CALL LEDGER" in printed
    assert "VERDICT: NON-DECISIVE" in printed


def test_decisive_config_rejects_mock_models(tmp_path):
    cfg = {
        "benchmark": {"families":["state","policy","reconciliation"],"complexities":[1],"qualities":[0.8],"seeds":[1],"epochs":1,"decisive":True,"minimum_primary_trials":1},
        "models": [{"provider":"mock","model":"mock"},{"provider":"mock","model":"mock2"},{"provider":"mock","model":"mock3"}]
    }
    path = tmp_path / "bad.yaml"; path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="mock"):
        load_config(path)


def test_environment_model_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODEL_NAME", "family-a-model")
    cfg = {"benchmark":{"decisive":False},"models":[{"provider":"ollama","model":"${TEST_MODEL_NAME}"}]}
    path = tmp_path / "env.yaml"; path.write_text(yaml.safe_dump(cfg))
    loaded = load_config(path)
    assert loaded["models"][0]["model"] == "family-a-model"
