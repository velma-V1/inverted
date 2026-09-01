from __future__ import annotations

from pathlib import Path

import yaml


def test_s0_workflow_is_zero_call_model_free_validation():
    workflow = Path(".github/workflows/test3-s0-validation.yml")
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert 'python-version: "3.14"' in text
    assert "python -m pytest" in text
    assert "test2_cli" in text and "model-free" in text
    assert "test3_s0_cli" in text and "validate-instrument" in text
    forbidden = ["OllamaAdapter", "ollama pull", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "run_local_campaign"]
    for item in forbidden:
        assert item not in text


def test_s0_config_freezes_zero_call_guardrails():
    data = yaml.safe_load(Path("configs/test3-s0.yaml").read_text(encoding="utf-8"))
    assert data["physical_model_call_ceiling"] == 0
    assert data["architecture_claims_authorized"] is False
    assert data["power"]["bootstrap_iterations"] == 20000
    assert data["power"]["seed"] == 20260901
