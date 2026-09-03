import json
from pathlib import Path

from inverted.harvest_d.d3_cli import load_d3_config, main


def test_default_d3_config_freezes_models_budget_and_sealed_partition():
    config = load_d3_config(Path("configs/harvest-d-d3.json"))
    assert config["max_calls"] == 1000
    assert config["models"]["SMALL_A"] == "qwen2.5:1.5b-instruct-q8_0"
    assert config["models"]["QWEN"] == "qwen3.5:9b-q8_0"
    assert config["cases_per_family"]["sealed"] == 2
    assert config["seeds"]["sealed"] != config["seeds"]["development"]


def test_model_free_cli_spends_zero_calls_and_builds_full_planner(tmp_path):
    rc = main([
        "--config", "configs/harvest-d-d3.json",
        "--output", str(tmp_path),
        "--model-free",
    ])
    assert rc == 0
    preflight = json.loads((tmp_path / "d3_preflight.json").read_text(encoding="utf-8"))
    master = json.loads((tmp_path / "00-HARVEST-D-D3-MASTER-INDEX.json").read_text(encoding="utf-8"))
    assert preflight["calls_used"] == 0
    assert preflight["planner_candidates"] > 100
    assert master["physical_model_calls"] == 0
    assert master["mode"] == "MODEL_FREE"


def test_model_free_cli_is_deterministic_for_plan_level_artifacts(tmp_path):
    first = tmp_path / "one"
    second = tmp_path / "two"
    assert main(["--config", "configs/harvest-d-d3.json", "--output", str(first), "--model-free"]) == 0
    assert main(["--config", "configs/harvest-d-d3.json", "--output", str(second), "--model-free"]) == 0
    for name in (
        "d3_coverage_matrix.json",
        "d3_data_dictionary.json",
        "d3_capture_completeness.json",
        "d3_data_value_audit.json",
        "d4_handoff.json",
    ):
        assert (first / name).read_text(encoding="utf-8") == (second / name).read_text(encoding="utf-8")


def test_powershell_launcher_model_free_gate_precedes_real_run_and_has_no_retry_loop():
    text = Path("scripts/run-harvest-d-d3.ps1").read_text(encoding="utf-8")
    model_free = text.index("--model-free")
    real = text.rindex("python -m inverted.harvest_d.d3_cli")
    assert model_free < real
    lowered = text.lower()
    assert "while (" not in lowered
    assert "start-sleep" not in lowered
    assert "retry until" not in lowered
