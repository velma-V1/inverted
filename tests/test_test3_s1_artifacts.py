from __future__ import annotations

import csv
import json
from pathlib import Path

from inverted.test3_s1_artifacts import REQUIRED_S1_FILES, Test3S1ArtifactWriter


def test_s1_writer_emits_hash_sealed_forensic_packet(tmp_path: Path):
    packet = tmp_path / "packet"
    evidence = {
        "preregistration": {"section": "S1_FIXED_STACK_ORDER", "exact_budget": 80},
        "config": {"s1": {"hard_call_limit": 80}},
        "provenance": {"run_id": "s1-test"},
        "model_calls": [{"call_id": "c1", "prompt": [{"role": "user", "content": "x"}], "response": "{}"}],
        "events": [{"event": "run_started"}],
        "trials": [{"task_id": "t1", "arm_id": "S1-A0", "success": True, "complete": True}],
        "validator_results": [{"task_id": "t1", "stage": "final", "deterministic_success": True}],
        "arm_summaries": [{"arm_id": "S1-A0", "matched_success_rate": 1.0}],
        "pairwise_effects": [{"arm_id": "S1-A1", "reference_arm_id": "S1-A0", "net_wins": 1}],
        "transitions": [{"task_id": "t1", "transition": "SUCCESS_TO_SUCCESS"}],
        "edge_cases": [{"classification": "test-edge"}],
        "instrumentation_anomalies": [],
        "verdict": {"verdict": "S1_SCREEN_NON_DECISIVE", "physical_model_calls": 1},
        "report": "S1 report\n",
    }
    Test3S1ArtifactWriter(packet).write_all(evidence)
    assert not [name for name in REQUIRED_S1_FILES if not (packet / name).exists()]
    assert "PHYSICAL MODEL CALLS" in (packet / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    with (packet / "SHA256SUMS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all((packet / row["path"]).is_file() for row in rows)
    index = json.loads((packet / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    assert index["section"] == "S1"
    assert index["physical_model_calls"] == 1
