from __future__ import annotations

import json

import inverted.capability_ratchet as api
from inverted.capability_ratchet.cli import main


PUBLIC_NAMES = (
    "CompilationKind",
    "CompilationEligibilityStatus",
    "CompilationDisposition",
    "CompilationCandidate",
    "CompilationPlan",
    "CompiledCapability",
    "CompilationPolicy",
    "CompilationEvidenceStore",
    "CompilationEligibilityScanner",
    "CompilationPlanner",
    "CapabilityCompiler",
    "plan_eligible_compilation",
)


def _roots(tmp_path):
    return {
        "replay": tmp_path / "replay",
        "causal": tmp_path / "causal",
        "surface": tmp_path / "surface",
        "mutation": tmp_path / "mutation",
        "tomography": tmp_path / "tomography",
        "compilation": tmp_path / "compilation",
    }


def _argv(command, roots, *extra):
    return [
        command,
        "--replay-root", str(roots["replay"]),
        "--causal-root", str(roots["causal"]),
        "--surface-root", str(roots["surface"]),
        "--mutation-root", str(roots["mutation"]),
        "--tomography-root", str(roots["tomography"]),
        "--compilation-root", str(roots["compilation"]),
        *extra,
    ]


def _stdout_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_stage8_minimum_public_api_is_exported():
    for name in PUBLIC_NAMES:
        assert hasattr(api, name), name
        assert name in api.__all__
    assert not hasattr(api, "CompilationExecutor")


def test_scan_compilation_eligibility_is_zero_call_on_empty_canonical_stores(tmp_path, capsys):
    roots = _roots(tmp_path)
    rc = main(_argv("scan-compilation-eligibility", roots))
    payload = _stdout_json(capsys)
    assert rc == 0
    assert payload == {
        "MODEL_CALLS": 0,
        "status": "COMPILATION_ELIGIBILITY_SCAN",
        "rows": [],
    }


def test_auto_plan_returns_scientific_empty_boundary_without_execution(tmp_path, capsys):
    roots = _roots(tmp_path)
    rc = main(_argv("plan-compilation", roots, "--auto-eligible"))
    payload = _stdout_json(capsys)
    assert rc == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["status"] == "NO_ELIGIBLE_COMPILATION_CANDIDATES"
    assert payload["plans"] == []
    assert payload["rows"] == []


def test_named_plan_missing_candidate_fails_without_model_calls(tmp_path, capsys):
    roots = _roots(tmp_path)
    rc = main(_argv("plan-compilation", roots, "--candidate-id", "missing-candidate"))
    captured = capsys.readouterr()
    assert rc == 2
    assert "missing-candidate" in captured.err


def test_empty_catalog_export_is_stable_zero_call_and_show_missing_is_safe(tmp_path, capsys):
    roots = _roots(tmp_path)
    output = tmp_path / "compiled-capabilities.json"
    rc = main(_argv("export-compiled-capabilities", roots, "--output", str(output)))
    payload = _stdout_json(capsys)
    assert rc == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["capabilities"] == []
    assert isinstance(payload["catalog_hash"], str) and len(payload["catalog_hash"]) == 64
    assert json.loads(output.read_text(encoding="utf-8")) == payload

    rc = main(_argv("show-compiled-capability", roots, "--capability-id", "missing-capability"))
    captured = capsys.readouterr()
    assert rc == 2
    assert "missing-capability" in captured.err


def test_stage8_cli_never_exposes_execution_authorization(tmp_path, capsys):
    roots = _roots(tmp_path)
    rc = main(_argv("scan-compilation-eligibility", roots))
    payload = _stdout_json(capsys)
    assert rc == 0 and payload["MODEL_CALLS"] == 0
    rendered = json.dumps(payload).lower()
    assert "allow-model-calls" not in rendered
    assert "execute-compilation" not in rendered
