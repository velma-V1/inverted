from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.harvest_d.hd_next2.config import HDNext2ConfigError, load_hd_next2_config
from inverted.harvest_d.hd_next2.types import DeliveryMode, StageId


CONFIG = Path("configs/harvest-d-hd-next-2a.json")


def test_hd_next2_config_freezes_program_invariants():
    cfg = load_hd_next2_config(CONFIG)
    assert cfg["experiment_id"] == "HD-NEXT-2A"
    assert cfg["combined_action_ceiling"] == 1000
    assert cfg["non_model_action_reserve"] >= 40
    assert cfg["protected_exploration_fraction"] >= 0.20
    assert cfg["blind_retries_allowed"] is False
    assert set(cfg["models"]) == {"SMALL_A", "QWEN", "DEVSTRAL_24B"}
    assert cfg["models"] == {
        "SMALL_A": "qwen2.5:1.5b-instruct-q8_0",
        "QWEN": "qwen3.5:9b-q8_0",
        "DEVSTRAL_24B": "devstral-small-2:24b",
    }
    assert StageId.A10.value == "2A-10"
    assert DeliveryMode.PROGRESSIVE.value == "PROGRESSIVE"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("combined_action_ceiling", 1001),
        ("combined_action_ceiling", 1000.9),
        ("combined_action_ceiling", "1000"),
        ("combined_action_ceiling", True),
        ("non_model_action_reserve", 39),
        ("non_model_action_reserve", "40"),
        ("non_model_action_reserve", False),
        ("protected_exploration_fraction", 0.19),
        ("protected_exploration_fraction", "0.20"),
        ("protected_exploration_fraction", True),
        ("stages", ["2A-unknown"]),
        ("primary_model", None),
        ("blind_retries_allowed", True),
    ],
    ids=[
        "rejects_unsafe_ceiling",
        "rejects_fractional_ceiling",
        "rejects_string_ceiling",
        "rejects_boolean_ceiling",
        "rejects_unsafe_reserve",
        "rejects_string_reserve",
        "rejects_boolean_reserve",
        "rejects_unsafe_exploration",
        "rejects_string_exploration",
        "rejects_boolean_exploration",
        "rejects_unknown_stage",
        "rejects_missing_primary_model",
        "rejects_blind_retries",
    ],
)
def test_hd_next2_config_rejects_mandated_unsafe_values(tmp_path, field, value):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config[field] = value
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(HDNext2ConfigError):
        load_hd_next2_config(candidate)


def test_hd_next2_config_freezes_exact_model_ids(tmp_path):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["models"]["QWEN"] = "arbitrary-model"
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(HDNext2ConfigError):
        load_hd_next2_config(candidate)
