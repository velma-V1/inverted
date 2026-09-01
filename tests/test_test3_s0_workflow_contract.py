from __future__ import annotations

from pathlib import Path

import yaml


def test_s0_workflow_is_zero_call_repo_backed_replay():
    workflow = Path(".github/workflows/test3-s0-validation.yml")
    replay = Path("scripts/run_test3_s0_from_repo.py")
    assert workflow.exists()
    assert replay.exists()

    workflow_text = workflow.read_text(encoding="utf-8")
    replay_text = replay.read_text(encoding="utf-8")
    workflow_data = yaml.safe_load(workflow_text)

    assert 'python-version: "3.14"' in workflow_text
    assert "python -m pytest" in workflow_text
    assert "run_test3_s0_from_repo.py" in workflow_text
    assert "repo-replay-summary.json" in workflow_text

    steps = workflow_data["jobs"]["test3-s0-repo-replay"]["steps"]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout.get("with", {}).get("lfs") is True

    assert "inverted.test2_cli" in replay_text and '"model-free"' in replay_text
    assert "inverted.test3_s0_cli" in replay_text and '"run"' in replay_text
    assert "verify_repo_evidence" in replay_text
    assert "DISCOVERY_COMPLETE_MODEL_FREE" in replay_text
    assert '"physical_model_calls"' in replay_text

    # model_calls.jsonl is a forensic preservation layer for historical source
    # model-call records. Zero NEW S0 inference is proven by the guard/verdict,
    # not by requiring that historical evidence file to be empty.
    assert 'verdict["physical_model_calls"] == 0' in workflow_text
    assert 'verdict["attempted_model_calls"] == 0' in workflow_text
    assert 'model_calls.jsonl").read_text' not in workflow_text

    combined = workflow_text + replay_text
    forbidden = ["OllamaAdapter", "ollama pull", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "run_local_campaign"]
    for item in forbidden:
        assert item not in combined


def test_s0_config_freezes_zero_call_guardrails():
    data = yaml.safe_load(Path("configs/test3-s0.yaml").read_text(encoding="utf-8"))
    assert data["physical_model_call_ceiling"] == 0
    assert data["architecture_claims_authorized"] is False
    assert data["power"]["bootstrap_iterations"] == 20000
    assert data["power"]["seed"] == 20260901
