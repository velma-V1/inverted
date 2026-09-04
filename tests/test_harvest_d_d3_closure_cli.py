import json
from pathlib import Path

from inverted.harvest_d.d3_closure_cli import load_closure_config, main


CONFIG = Path("configs/harvest-d-d3-closure-v2.json")


def test_closure_config_freezes_budget_retry_and_fresh_seed_contract():
    config = load_closure_config(CONFIG)
    assert config["protocol"] == "D3-CLOSURE-v2"
    assert config["max_calls"] == 200
    assert config["sealed_reserve"] == 48
    assert config["blind_retries_allowed"] is False
    seeds = config["seeds"]
    assert len(set(seeds.values())) == 3
    assert set(seeds.values()).isdisjoint({20260903, 20260913, 20261003})


def test_model_free_cli_succeeds_without_ollama_and_writes_master(tmp_path: Path):
    rc = main(["--config", str(CONFIG), "--output", str(tmp_path), "--model-free"])
    assert rc == 0
    master = json.loads((tmp_path / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json").read_text())
    assert master["physical_model_calls"] == 0


def test_real_cli_fails_closed_until_d4_policy_is_frozen(tmp_path: Path):
    rc = main(["--config", str(CONFIG), "--output", str(tmp_path)])
    assert rc == 2
