from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

from inverted.capability_ratchet import cli


def _module(filename: str, name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_auto_surface_plan_materializes_movement_reuses_answered_points_and_imports_v2_priors(
    tmp_path, capsys
) -> None:
    lab_tests = _module("test_capability_ratchet_surface_lab.py", "_surface_lab_completion")
    evidence_tests = _module("test_capability_ratchet_surface_evidence.py", "_surface_evidence_completion")
    case = lab_tests.build_case(tmp_path / "case")
    calls_before = len(case.adapter.calls)

    # Prove Stage-5 can be rebuilt from canonical replay + causal evidence rather
    # than depending on test-created surface metadata.
    shutil.rmtree(case.surface.root)
    source = evidence_tests._write_mini_v2(tmp_path / "v2", budget=1024)

    code = cli.main([
        "plan-surface",
        "--replay-root", str(case.replay.root),
        "--causal-root", str(case.causal.root),
        "--surface-root", str(case.surface.root),
        "--auto-eligible",
        "--source", str(source),
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "SURFACE_PLAN_READY"
    assert payload["MODEL_CALLS"] == 0
    assert payload["eligible_mechanisms"] == ["mechanism-surface"]
    assert len(case.adapter.calls) == calls_before
    assert payload["plans"]

    plan = payload["plans"][0]
    reused = {(row["axis"], row["value"]) for row in plan["reused_points"]}
    assert ("REASONING_BUDGET", 0) in reused
    assert ("REASONING_BUDGET", 512) in reused
    assert plan["historical_prior_count"] > 0
    proposed = {(row["axis"], row["value"]) for row in plan["plan"]["points"]}
    assert ("REASONING_BUDGET", 0) not in proposed
    assert ("REASONING_BUDGET", 512) not in proposed
    assert plan["unresolved_points"]
    assert plan["plan"]["decision_reason"]
    assert plan["plan"]["call_geometry"]["worst_case"] >= plan["plan"]["call_geometry"]["minimum"]


def test_auto_surface_plan_reports_no_eligible_mechanisms_without_manufacturing_movement(
    tmp_path, capsys
) -> None:
    cli_tests = _module("test_capability_ratchet_surface_cli.py", "_surface_cli_completion")
    replay_root = cli_tests._valid_replay_root(tmp_path)

    code = cli.main([
        "plan-surface",
        "--replay-root", str(replay_root),
        "--causal-root", str(tmp_path / "causal"),
        "--surface-root", str(tmp_path / "surface"),
        "--auto-eligible",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload == {
        "MODEL_CALLS": 0,
        "eligible_mechanisms": [],
        "plans": [],
        "status": "NO_ELIGIBLE_MECHANISMS",
    }
