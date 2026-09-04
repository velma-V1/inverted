from pathlib import Path


CHAIN = Path("scripts/run-harvest-d-d4-through-closure.ps1")
WORKFLOW = Path(".github/workflows/harvest-d-validation.yml")


def test_chain_launcher_sequentially_hands_d4_to_closure_readiness():
    assert CHAIN.exists(), "automatic D4->Closure launcher is missing"
    text = CHAIN.read_text(encoding="utf-8")
    lower = text.lower()
    assert "d4->closure chain: d4 real campaign" in lower
    assert "d4->closure chain: closure readiness gate" in lower
    assert "d4->closure chain: closure real campaign" in lower
    assert lower.index("d4->closure chain: d4 real campaign") < lower.index("d4->closure chain: closure readiness gate")
    assert lower.index("d4->closure chain: closure readiness gate") < lower.index("d4->closure chain: closure real campaign")
    assert lower.index("physical_execution_authorized") < lower.index("d4->closure chain: closure real campaign")
    assert lower.index("closure_claim_adequacy_report.json") < lower.index("d4->closure chain: closure real campaign")
    assert "d4_frozen_policy.json" in lower
    assert "model_digest" in lower
    assert "d4_complete_closure_scientific_hold" in lower
    assert "00-d4-through-closure-state.json" in lower
    assert "start-process" not in lower
    assert "start-job" not in lower


def test_chain_model_free_mode_runs_both_real_launchers_without_inference():
    assert CHAIN.exists(), "automatic D4->Closure launcher is missing"
    text = CHAIN.read_text(encoding="utf-8")
    lower = text.lower()
    assert "run-harvest-d-d4-qwen-policy.ps1" in lower
    assert "run-harvest-d-d3-closure-v2.ps1" in lower
    assert lower.count("-modelfreeonly") >= 2


def test_windows_ci_executes_the_combined_model_free_chain():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "run-harvest-d-d4-through-closure.ps1" in text
    assert "D4 through Closure PowerShell launcher model-free gate" in text
