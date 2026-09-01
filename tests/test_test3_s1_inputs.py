from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.test3_s1_inputs import load_s1_inputs


def _packet(tmp_path: Path, *, frozen: bool = True, oracle: bool = False) -> Path:
    s0 = tmp_path / "s0"
    t2 = tmp_path / "test2-tier-a"
    (t2 / "models").mkdir(parents=True)
    s0.mkdir()

    order = "requirement_validator -> retry -> targeted_repair -> final_validator"
    if oracle:
        order = "oracle_auditor -> retry -> final_validator"
    prereg = {
        "status": "S1_SCREEN_FROZEN_AWAITING_TIER_A_AUTHORIZATION" if frozen else "CANDIDATE_ONLY_NOT_PREREGISTERED",
        "section": "S1_FIXED_STACK_ORDER",
        "holdout": "A",
        "arm_freeze_ready": frozen,
        "exact_budget": 80 if frozen else None,
        "arm_count": 4,
        "physical_call_cap_per_arm": 20,
        "tier_a_inference_authorized": False,
        "arms": [
            {"arm_id": "S1-A0", "role": "best_single_model_baseline", "order": None, "physical_call_cap": 20},
            {"arm_id": "S1-A1", "role": "current_best_fixed_hybrid", "order": order, "physical_call_cap": 20},
            {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "retry -> requirement_validator -> targeted_repair -> final_validator", "physical_call_cap": 20},
            {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "targeted_repair -> retry -> requirement_validator -> final_validator", "physical_call_cap": 20},
        ],
        "power_evidence": {"recommended_clusters": 260},
    }
    (s0 / "candidate_section1_preregistration.json").write_text(json.dumps(prereg), encoding="utf-8")
    (s0 / "source_manifest.json").write_text(json.dumps({"sources": [
        {"source_id": "test2-tier-a", "source_class": "test2_tier_a", "path": str(t2), "required": True}
    ]}), encoding="utf-8")
    (t2 / "models" / "router-policy.json").write_text(json.dumps({
        "best_single_model": {"model": "qwen3.5:9b-q8_0", "successes": 10}
    }), encoding="utf-8")
    (t2 / "models" / "role-champions.json").write_text(json.dumps({
        "formalizer": "qwen3.5:9b-q8_0",
        "executor": "qwen3.5:9b-q8_0",
        "repairer": "llama3.1:8b",
        "auditor": "granite4:7b-a1b-h",
    }), encoding="utf-8")
    return s0


def test_load_s1_inputs_resolves_frozen_models_and_budget(tmp_path: Path):
    resolved = load_s1_inputs(_packet(tmp_path))
    assert resolved.best_single_model == "qwen3.5:9b-q8_0"
    assert resolved.repair_model == "llama3.1:8b"
    assert resolved.exact_budget == 80
    assert resolved.per_arm_call_cap == 20
    assert len(resolved.arms) == 4
    assert resolved.holdout == "A"
    assert resolved.full_power_clusters == 260


def test_load_s1_inputs_rejects_unfrozen_packet(tmp_path: Path):
    with pytest.raises(ValueError, match="not frozen"):
        load_s1_inputs(_packet(tmp_path, frozen=False))


def test_load_s1_inputs_rejects_analysis_only_oracle_arm(tmp_path: Path):
    with pytest.raises(ValueError, match="analysis-only"):
        load_s1_inputs(_packet(tmp_path, oracle=True))
