from pathlib import Path


D4_SCRIPT = Path("scripts/run-harvest-d-d4-qwen-policy.ps1")
CLOSURE_SCRIPT = Path("scripts/run-harvest-d-d3-closure-v2.ps1")
WORKFLOW = Path(".github/workflows/harvest-d-validation.yml")


def test_d4_launcher_runs_model_free_gate_before_real_calls():
    text = D4_SCRIPT.read_text(encoding="utf-8")
    lower = text.lower()
    assert "d4 qwen policy gate: focused model-free tests" in lower
    assert "--model-free" in text
    assert "d4 qwen policy real local campaign" in lower
    assert lower.index("--model-free") < lower.index("d4 qwen policy real local campaign")
    assert "no model calls were started" in lower


def test_closure_launcher_automatically_obtains_d4_policy_before_real_campaign():
    text = CLOSURE_SCRIPT.read_text(encoding="utf-8")
    lower = text.lower()
    assert "run-harvest-d-d4-qwen-policy.ps1" in lower
    assert "d4_frozen_policy.json" in lower
    assert "--d4-policy-file" in text
    assert lower.index("run-harvest-d-d4-qwen-policy.ps1") < lower.index("d3-closure v2 real local campaign")


def test_harvest_d_ci_runs_d4_zero_call_contract():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "inverted.harvest_d.d4_qwen_cli" in text
    assert "harvest-d-d4-qwen-policy.json" in text
    assert "test_harvest_d_d4_qwen_*.py" in text
