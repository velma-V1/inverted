from pathlib import Path


SCRIPT = Path("scripts/run-harvest-d-d3-closure-v2.ps1")
WORKFLOW = Path(".github/workflows/harvest-d-validation.yml")


def test_closure_launcher_runs_focused_gate_before_any_real_campaign():
    text = SCRIPT.read_text(encoding="utf-8")
    lower = text.lower()
    assert "d3-closure v2 gate: focused model-free tests" in lower
    assert "--model-free" in text
    assert "d3-closure v2 real local campaign" in lower
    assert lower.index("--model-free") < lower.index("d3-closure v2 real local campaign")
    assert "no model calls were started" in lower


def test_harvest_d_ci_runs_closure_tests_and_zero_call_package():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "test_harvest_d_d3_closure_*.py" in text
    assert "inverted.harvest_d.d3_closure_cli" in text
    assert "harvest-d-d3-closure-v2.json" in text
