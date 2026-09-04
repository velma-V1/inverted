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
    assert "-ModelFreeOnly" in text
    assert "--model-free" in text
    assert "MaxCalls -gt 24" in text
    assert "run-harvest-d-d3-closure-v2.ps1" not in text
    assert "Start-Process" not in text
    assert "Start-Job" not in text


def test_r1_launcher_requires_fresh_r0_and_exact_d4_policy_before_real_calls():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "closure_r0_readiness_report.json" in text
    assert "R0_MODEL_FREE_COMPLETE" in text
    assert "d4_frozen_policy.json" in text
    assert "model_digest" in text
    assert "stage_physical_execution_authorized" in text
    assert "legacy_closure_physical_execution_authorized" in text


def test_windows_ci_executes_r1_model_free_launcher():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "run-harvest-d-d3-closure-r1.ps1" in text
    assert "R1 PowerShell launcher model-free gate" in text
    assert "-ModelFreeOnly" in text
