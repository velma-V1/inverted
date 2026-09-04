import json
from pathlib import Path

from inverted.harvest_d.d3_closure_cli import load_frozen_d4_policy
from inverted.harvest_d.d4_qwen_cli import load_d4_config, main


CONFIG = Path("configs/harvest-d-d4-qwen-policy.json")


def test_d4_config_freezes_model_budget_and_two_policy_contract():
    config = load_d4_config(CONFIG)
    assert config["protocol"] == "D4-QWEN-POLICY-v1"
    assert config["max_calls"] == 48
    assert config["model"] == "qwen3.5:9b-q8_0"
    assert set(config["policies"]) == {"DEFAULT", "THINK_OFF"}
    assert config["policies"]["THINK_OFF"]["chat_options"] == {"think": False}
    assert config["blind_retries_allowed"] is False


def test_d4_model_free_cli_succeeds_without_ollama(tmp_path: Path):
    rc = main(["--config", str(CONFIG), "--output", str(tmp_path), "--model-free"])
    assert rc == 0
    policy = json.loads((tmp_path / "d4_frozen_policy.json").read_text())
    assert policy["state"] == "NOT_RUN"


def test_closure_loads_frozen_d4_policy_without_editing_tracked_config(tmp_path: Path):
    path = tmp_path / "d4_frozen_policy.json"
    path.write_text(json.dumps({
        "state": "FROZEN",
        "policy_id": "THINK_OFF",
        "model_id": "qwen3.5:9b-q8_0",
        "chat_options": {"think": False},
        "matched_cases": 24,
        "semantic_decision": "SUPERIOR",
    }), encoding="utf-8")
    policy = load_frozen_d4_policy(path, expected_model="qwen3.5:9b-q8_0")
    assert policy["policy_id"] == "THINK_OFF"
    assert policy["chat_options"] == {"think": False}


def test_closure_rejects_unresolved_d4_policy(tmp_path: Path):
    path = tmp_path / "d4_frozen_policy.json"
    path.write_text(json.dumps({
        "state": "UNRESOLVED",
        "policy_id": None,
        "model_id": "qwen3.5:9b-q8_0",
        "chat_options": {},
    }), encoding="utf-8")
    try:
        load_frozen_d4_policy(path, expected_model="qwen3.5:9b-q8_0")
    except ValueError as exc:
        assert "not frozen" in str(exc).lower()
    else:
        raise AssertionError("unresolved D4 policy must be rejected")
