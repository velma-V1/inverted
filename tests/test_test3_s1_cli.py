from __future__ import annotations

import json
from pathlib import Path

from inverted.test3_s1_cli import main


def _frozen_packet(tmp_path: Path) -> Path:
    s0 = tmp_path / "s0"
    t2 = tmp_path / "t2"
    (t2 / "models").mkdir(parents=True)
    s0.mkdir()
    prereg = {
        "status": "S1_SCREEN_FROZEN_AWAITING_TIER_A_AUTHORIZATION",
        "section": "S1_FIXED_STACK_ORDER",
        "holdout": "A",
        "arm_freeze_ready": True,
        "exact_budget": 80,
        "arm_count": 4,
        "physical_call_cap_per_arm": 20,
        "tier_a_inference_authorized": False,
        "arms": [
            {"arm_id": "S1-A0", "role": "best_single_model_baseline", "order": None, "physical_call_cap": 20},
            {"arm_id": "S1-A1", "role": "current_best_fixed_hybrid", "order": "requirement_validator -> retry -> targeted_repair -> final_validator", "physical_call_cap": 20},
            {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "retry -> requirement_validator -> targeted_repair -> final_validator", "physical_call_cap": 20},
            {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "targeted_repair -> retry -> requirement_validator -> final_validator", "physical_call_cap": 20},
        ],
        "power_evidence": {"recommended_clusters": 260},
    }
    (s0 / "candidate_section1_preregistration.json").write_text(json.dumps(prereg), encoding="utf-8")
    (s0 / "source_manifest.json").write_text(json.dumps({"sources": [{"source_class": "test2_tier_a", "source_id": "t2", "path": str(t2)}]}), encoding="utf-8")
    (t2 / "models" / "router-policy.json").write_text(json.dumps({"best_single_model": {"model": "qwen3.5:9b-q8_0"}}), encoding="utf-8")
    (t2 / "models" / "role-champions.json").write_text(json.dumps({"repairer": "llama3.1:8b"}), encoding="utf-8")
    return s0


def test_dry_plan_reports_frozen_budget_without_inference(tmp_path: Path, capsys):
    rc = main(["dry-plan", "--s0-dir", str(_frozen_packet(tmp_path)), "--config", "configs/test3-s1.yaml"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "EXACT_BUDGET=80" in out
    assert "ARM_COUNT=4" in out
    assert "TIER_A_INFERENCE_AUTHORIZED=false" in out


def test_run_refuses_without_explicit_tier_a_authorization(tmp_path: Path, capsys):
    rc = main([
        "run", "--s0-dir", str(_frozen_packet(tmp_path)), "--config", "configs/test3-s1.yaml",
        "--output-dir", str(tmp_path / "out"), "--run-id", "s1-test",
    ])
    assert rc == 2
    assert "TIER_A_AUTHORIZATION_REQUIRED" in capsys.readouterr().err


def test_mock_smoke_writes_validation_packet_without_real_inference(tmp_path: Path):
    out = tmp_path / "mock"
    rc = main(["mock-smoke", "--output-dir", str(out), "--run-id", "s1-mock"])
    assert rc == 0
    verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["verdict"] == "MOCK_VALIDATION_ONLY"
    assert verdict["tier_a_architecture_claim"] is False
    assert verdict["real_model_inference"] is False
