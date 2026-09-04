from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run-harvest-d-d3-closure-r1.ps1"
AUTH = ROOT / "configs" / "harvest-d-d3-closure-v2-r1-authorization.json"
WORKFLOW = ROOT / ".github" / "workflows" / "harvest-d-validation.yml"


def test_r1_stage_authorization_exists_and_cannot_authorize_legacy_closure():
    payload = json.loads(AUTH.read_text(encoding="utf-8"))
    assert payload["protocol"] == "D3-CLOSURE-v2"
    assert payload["stage"] == "R1_CALIBRATION"
    assert payload["max_physical_calls"] == 24
    assert payload["stage_physical_execution_authorized"] is True
    assert payload["legacy_closure_physical_execution_authorized"] is False


def test_r1_launcher_runs_fresh_r0_then_r1_model_free_before_any_physical_path():
    text = SCRIPT.read_text(encoding="utf-8")
    r0 = text.index("d3_closure_cli")
    r1 = text.index("d3_closure_r1_cli")
    auth = text.index("$Stage = Get-Content")
    real = text.index("R1 calibration real local campaign")
    assert r0 < r1 < auth < real
    assert "[switch]$ModelFreeOnly" in text
    assert "--model-free" in text
    assert "MaxCalls -gt 24" in text
    assert "run-harvest-d-d3-closure-v2.ps1" not in text
    assert "Start-Process" not in text
    assert "Start-Job" not in text


def test_r1_launcher_materializes_pinned_frozen_d3_when_local_run_is_absent():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "4463d1f596c7126be17257e6008432b49d2bacde" in text
    assert "evidence/harvest-d-d3-20260903" in text
    assert "live-evidence/harvest-d-d3-real-20260903-185137/D3-COMPLETE-CAMPAIGN.zip" in text
    assert "371588D6C5616D371E7EF891E939271F0AF09AC6462A0DF00F8B1486CFC4AC2B" in text
    assert "git fetch origin" in text
    assert "git archive --format=zip" in text
    assert "Get-FileHash" in text
    assert "Expand-Archive" in text
    assert "00-HARVEST-D-D3-MASTER-INDEX.json" in text


def test_r1_model_free_windows_gate_exercises_frozen_d3_resolution_and_revalidation():
    text = SCRIPT.read_text(encoding="utf-8")
    resolve = text.index("R1 prerequisite: resolve frozen D3-v1 evidence")
    post_d3 = text.index("post_d3_cli")
    model_free_exit = text.index("if ($ModelFreeOnly)")
    assert resolve < post_d3 < model_free_exit


def test_r1_launcher_recovers_original_completed_d4_without_rerunning_d4():
    text = SCRIPT.read_text(encoding="utf-8")
    model_free_exit = text.index("if ($ModelFreeOnly)")
    d4_resolve = text.index("inverted.harvest_d.d4_evidence")
    real = text.index("R1 calibration real local campaign")
    assert model_free_exit < d4_resolve < real
    assert "--preferred-root" in text
    assert "--search-root" in text
    assert "--recovery-root" in text
    assert "--expected-model" in text
    assert "d4_evidence_resolution.json" in text
    assert "d4_rerun_performed" in text
    assert "policy_file" in text
    assert "run-harvest-d-d4-qwen-policy.ps1" not in text
    assert "d4_qwen_cli" not in text


def test_r1_launcher_requires_fresh_r0_historical_d3_and_exact_d4_policy_before_real_calls():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "closure_r0_readiness_report.json" in text
    assert "R0_MODEL_FREE_COMPLETE" in text
    assert "post_d3_cli" in text
    assert "post_d3_gap_registry.json" in text
    assert "--historical-gap-registry" in text
    assert "d4_frozen_policy.json" in text
    assert "model_digest" in text
    assert "stage_physical_execution_authorized" in text
    assert "legacy_closure_physical_execution_authorized" in text


def test_windows_ci_executes_r1_model_free_launcher():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "run-harvest-d-d3-closure-r1.ps1" in text
    assert "R1 PowerShell launcher model-free gate" in text
    assert "-ModelFreeOnly" in text
