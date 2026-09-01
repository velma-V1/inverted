from __future__ import annotations

import csv
import json
from pathlib import Path

from inverted.test3_s1_artifacts import REQUIRED_S1_FILES, Test3S1ArtifactWriter


def test_s1_writer_emits_hash_sealed_forensic_packet_with_protocol_gate(tmp_path: Path):
    packet = tmp_path / "packet"
    evidence = {
        "preregistration": {
            "section": "S1_FIXED_STACK_ORDER",
            "protocol_revision": "S1-R2",
            "holdout": "A-R2",
            "exact_budget": 200,
            "source_s0_screen_budget": 80,
        },
        "config": {"s1": {"protocol_revision": "S1-R2", "holdout": "A-R2", "hard_call_limit": 200}},
        "provenance": {"run_id": "s1-r2-test", "protocol_revision": "S1-R2", "execution_holdout": "A-R2"},
        "model_calls": [{"call_id": "c1", "prompt": [{"role": "user", "content": "x"}], "response": "{}", "active_intervention": True, "shadow_only": False}],
        "events": [{"event": "run_started", "protocol_revision": "S1-R2", "execution_mode": "balanced_task_blocks"}],
        "trials": [{
            "protocol_revision": "S1-R2", "holdout": "A-R2", "task_id": "t1", "arm_id": "S1-A0",
            "family": "repair_containment", "success": True, "complete": True, "seed_failure_verified": True,
            "active_inference_calls": 1, "shadow_inference_calls": 1, "physical_calls_added": 2,
            "task_index": 0, "arm_execution_position": 0, "execution_ordinal": 0,
            "seed_passed_requirements": ["p1"], "seed_failed_requirements": ["f1"],
            "final_passed_requirements": ["p1", "f1"], "final_failed_requirements": [],
            "requirement_kinds": {"p1": "preserve", "f1": "equal"},
        }],
        "validator_results": [{"task_id": "t1", "stage": "final", "deterministic_success": True}],
        "arm_summaries": [{"arm_id": "S1-A0", "matched_success_rate": 1.0}],
        "family_summaries": [{
            "family": "repair_containment", "task_count": 5,
            "arm_summaries": [{"arm_id": "S1-A0", "requirements_repaired": 1, "requirements_regressed": 0}],
            "pairwise_effects": [],
        }],
        "pairwise_effects": [{"arm_id": "S1-A1", "reference_arm_id": "S1-A0", "net_wins": 1}],
        "transitions": [{"task_id": "t1", "transition": "SUCCESS_TO_SUCCESS"}],
        "intervention_exposure": {
            "all_seed_failures_verified": True,
            "all_arm_tasks_have_active_intervention": True,
            "distinct_fixed_first_active_components": 2,
        },
        "protocol_failures": [],
        "edge_cases": [{"classification": "test-edge"}],
        "instrumentation_anomalies": [],
        "verdict": {
            "verdict": "S1_R2_SCREEN_NON_DECISIVE",
            "physical_model_calls": 200,
            "matched_task_count": 25,
            "protocol_valid_for_primary_claim": True,
            "protocol_revision": "S1-R2",
            "holdout": "A-R2",
        },
        "report": "S1-R2 report\n",
    }
    Test3S1ArtifactWriter(packet).write_all(evidence)
    assert not [name for name in REQUIRED_S1_FILES if not (packet / name).exists()]
    assert "PHYSICAL MODEL CALLS" in (packet / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    assert "S1-R2" in (packet / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    with (packet / "SHA256SUMS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all((packet / row["path"]).is_file() for row in rows)
    index = json.loads((packet / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    exposure = json.loads((packet / "intervention_exposure.json").read_text(encoding="utf-8"))
    assert index["section"] == "S1"
    assert index["physical_model_calls"] == 200
    assert index["protocol_revision"] == "S1-R2"
    assert index["holdout"] == "A-R2"
    assert index["protocol_valid_for_primary_claim"] is True
    assert index["family_count"] == 1
    assert exposure["distinct_fixed_first_active_components"] == 2
    assert (packet / "family_summaries.csv").is_file()
