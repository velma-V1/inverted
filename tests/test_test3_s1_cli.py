from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from inverted.test3_s1_cli import InPlaceS1Progress, main


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
            {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "requirement_validator -> targeted_repair -> final_validator -> retry", "physical_call_cap": 20},
            {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "retry -> targeted_repair -> final_validator -> requirement_validator", "physical_call_cap": 20},
        ],
        "power_evidence": {"recommended_clusters": 260},
    }
    (s0 / "candidate_section1_preregistration.json").write_text(json.dumps(prereg), encoding="utf-8")
    (s0 / "source_manifest.json").write_text(json.dumps({"sources": [{"source_class": "test2_tier_a", "source_id": "t2", "path": str(t2)}]}), encoding="utf-8")
    (t2 / "models" / "router-policy.json").write_text(json.dumps({"best_single_model": {"model": "qwen3.5:9b-q8_0"}}), encoding="utf-8")
    (t2 / "models" / "role-champions.json").write_text(json.dumps({"repairer": "cogito:3b-v1-preview-llama-q8_0"}), encoding="utf-8")
    return s0


def test_dry_plan_reports_r2_exact_200_call_schedule_and_preserves_s0_budget_provenance(tmp_path: Path, capsys):
    rc = main(["dry-plan", "--s0-dir", str(_frozen_packet(tmp_path)), "--config", "configs/test3-s1.yaml"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROTOCOL=S1-R2" in out
    assert "HOLDOUT=A-R2" in out
    assert "EXACT_BUDGET=200" in out
    assert "SOURCE_S0_SCREEN_BUDGET=80" in out
    assert "ARM_COUNT=4" in out
    assert "PER_ARM_CALL_CAP=50" in out
    assert "MATCHED_TASKS=25" in out
    assert "CALLS_PER_ARM_TASK=2" in out
    assert "PLANNED_PHYSICAL_CALLS=200" in out
    assert "EXECUTION_MODE=balanced_task_blocks" in out
    assert "INTERVENTION_START=deterministic_verified_failure" in out
    assert "BEST_SINGLE_MODEL=qwen3.5:9b-q8_0" in out
    assert "REPAIR_MODEL=cogito:3b-v1-preview-llama-q8_0" in out
    assert "TIER_A_INFERENCE_AUTHORIZED=false" in out


def test_run_refuses_without_explicit_tier_a_authorization(tmp_path: Path, capsys):
    rc = main([
        "run", "--s0-dir", str(_frozen_packet(tmp_path)), "--config", "configs/test3-s1.yaml",
        "--output-dir", str(tmp_path / "out"), "--run-id", "s1-r2-test",
    ])
    assert rc == 2
    assert "TIER_A_AUTHORIZATION_REQUIRED" in capsys.readouterr().err


def test_mock_smoke_writes_exact_200_call_r2_validation_packet(tmp_path: Path):
    out = tmp_path / "mock"
    rc = main(["mock-smoke", "--output-dir", str(out), "--run-id", "s1-r2-mock"])
    assert rc == 0
    verdict = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    master = json.loads((out / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    prereg = json.loads((out / "preregistration.json").read_text(encoding="utf-8"))
    assert verdict["verdict"] == "MOCK_VALIDATION_ONLY"
    assert verdict["tier_a_architecture_claim"] is False
    assert verdict["real_model_inference"] is False
    assert verdict["physical_model_calls"] == 200
    assert verdict["matched_task_count"] == 25
    assert verdict["protocol_valid_for_primary_claim"] is True
    assert master["protocol_revision"] == "S1-R2"
    assert master["holdout"] == "A-R2"
    assert master["physical_model_calls"] == 200
    assert master["trial_rows"] == 100
    assert master["family_count"] == 6
    assert prereg["source_s0_screen_budget"] == 80
    assert prereg["exact_budget"] == 200
    assert (out / "family_summaries.csv").is_file()


def test_r2_config_rejects_stale_r1_protocol(tmp_path: Path):
    stale = tmp_path / "stale.yaml"
    stale.write_text(
        "s1:\n"
        "  section: S1_FIXED_STACK_ORDER\n"
        "  protocol_revision: S1-R1\n"
        "  holdout: A-R1\n"
        "  hard_call_limit: 80\n"
        "  arm_count: 4\n"
        "  per_arm_call_cap: 20\n"
        "  matched_tasks: 10\n"
        "  calls_per_arm_task: 2\n"
        "  intervention_start: deterministic_verified_failure\n"
        "  predecessor_invalid_run: test3-s1-20260901-111233\n"
        "  predecessor_invalidation: INTERVENTION_EXPOSURE_COLLAPSE\n"
        "  no_outcome_dependent_early_stopping: true\n"
        "  ollama:\n"
        "    transport_retries: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="S1-R2 config protocol_revision"):
        main(["dry-plan", "--s0-dir", str(_frozen_packet(tmp_path)), "--config", str(stale)])


def test_s1_progress_rewrites_one_short_terminal_line_for_200_call_r2_and_finishes_once():
    stream = io.StringIO()
    progress = InPlaceS1Progress(stream=stream, width=16)

    progress.update(
        completed_tasks=1,
        total_tasks=100,
        physical_calls=2,
        call_budget=200,
        arm_id="S1-A2",
        task_id="test3-s1-AR2-repair_containment-L4-stress-long-id-that-must-not-wrap",
    )
    progress.update(
        completed_tasks=100,
        total_tasks=100,
        physical_calls=200,
        call_budget=200,
        arm_id="S1-A1",
        task_id="test3-s1-AR2-state-L2-another-long-id",
    )
    progress.finish()

    text = stream.getvalue()
    updates = [chunk for chunk in text.split("\r") if chunk and chunk != "\n"]
    assert text.count("\n") == 1
    assert text.count("\r") == 2
    assert "100/100" in text
    assert "200/200 calls" in text
    assert all(len(update.rstrip("\n")) <= 63 for update in updates)
