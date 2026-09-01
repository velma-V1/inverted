from __future__ import annotations

import json
from pathlib import Path

import yaml

from inverted.test3_s0_cli import main


def test_validate_instrument_accepts_partial_sources_and_emits_partial_verdict(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({
        "experiment": "test3-section0-github-causal-discovery",
        "mode": "model-free",
        "physical_model_call_ceiling": 0,
        "architecture_claims_authorized": False,
        "required_source_classes": ["test1", "test2_tier_a", "test2_model_free"],
        "allow_partial_instrument_validation": True,
    }), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": []}), encoding="utf-8")
    out = tmp_path / "out"
    rc = main(["validate-instrument", "--config", str(config), "--manifest", str(manifest), "--output-dir", str(out)])
    assert rc == 0
    verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["verdict"] == "PARTIAL_INPUT_EVIDENCE"
    assert verdict["physical_model_calls"] == 0


def test_run_refuses_missing_required_sources(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({
        "experiment": "test3-section0-github-causal-discovery",
        "mode": "model-free",
        "physical_model_call_ceiling": 0,
        "architecture_claims_authorized": False,
        "required_source_classes": ["test1"],
        "allow_partial_instrument_validation": True,
    }), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": []}), encoding="utf-8")
    rc = main(["run", "--config", str(config), "--manifest", str(manifest), "--output-dir", str(tmp_path / "out")])
    assert rc != 0


def test_cli_source_does_not_import_model_adapter():
    import inverted.test3_s0_cli as cli
    text = Path(cli.__file__).read_text(encoding="utf-8")
    assert "OllamaAdapter" not in text
    assert "run_local_campaign" not in text
    assert "from .models" not in text
