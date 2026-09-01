import csv
import json
from pathlib import Path

from inverted.test2_artifacts import Test2ArtifactWriter


def _minimal_evidence():
    return {
        "master_index": {"run_id": "t2", "physical_model_calls": 1},
        "raw": {
            "trials": [{"trial_id": "t", "success": True}],
            "model_calls": [{"call_id": "c", "model": "m"}],
            "prompts": [{"call_id": "c", "text": "PROMPT-SENTINEL"}],
            "responses": [{"call_id": "c", "text": "RESPONSE-SENTINEL"}],
            "candidates": [{"candidate_id": "x"}],
            "events": [{"event": "x"}],
            "validator_results": [{"ok": True}],
            "repairs": [{"fixed": True}],
        },
        "effects": {
            "outcome_transitions": [{"transition": "FAIL_TO_SUCCESS"}],
            "standalone_effects": [{"component": "validator", "net_wins": 1}],
            "progressive_effects": [],
            "ablation_effects": [],
            "pairwise_interactions": [],
            "failure_kill_matrix": [],
            "synergy_matrix": [],
        },
        "order": {
            "every_valid_order": [],
            "order_ranking": [],
            "order_slice_ranking": [],
            "every_valid_production_order": [{"order": "validator -> retry -> repair -> final", "production_eligible": True}],
            "production_order_ranking": [{"rank": 1, "order": "validator -> retry -> repair -> final", "production_eligible": True}],
            "production_order_slice_ranking": [],
            "saturation": [],
        },
        "models": {
            "model_task_capability_matrix": [],
            "model_family_matrix": [],
            "model_fault_matrix": [],
            "model_complexity_curves": [],
            "model_representation_matrix": [],
            "model_pair_synergy": [],
            "model_correlated_failures": [],
            "model_unique_wins": [],
            "role_champions": {"executor": "m"},
            "router_policy": {"executor": "m"},
            "router_holdout_results": [],
            "router_regret": [],
        },
        "thresholds": {
            "break_even": [], "plus_1pp": [], "plus_3pp": [], "plus_5pp": [], "plus_10pp": []
        },
        "provenance": {
            "config": {"x": 1}, "environment": {}, "git": {}, "models": {}
        },
        "next_stride_report": "NEXT-STRIDE-SENTINEL\n",
    }


def test_test2_writer_creates_required_forensic_bundle_and_master_contains_every_text_artifact(tmp_path):
    run_dir = tmp_path / "test2"
    paths = Test2ArtifactWriter(run_dir).write_all(_minimal_evidence())
    required = {
        "00-MASTER-INDEX.json",
        "raw/every-trial.jsonl",
        "raw/every-model-call.jsonl",
        "raw/every-prompt.jsonl",
        "raw/every-response.jsonl",
        "effects/outcome-transitions.csv",
        "order/every-valid-production-order.csv",
        "order/order-ranking-production.csv",
        "order/order-slice-ranking-production.csv",
        "models/role-champions.json",
        "models/router-policy.json",
        "TEST2-COMPLETE-EVIDENCE.txt",
        "TEST2-NEXT-STRIDE-REPORT.txt",
        "SHA256SUMS.csv",
    }
    assert required <= {str(Path(p).relative_to(run_dir)).replace("\\", "/") for p in paths.values()}

    production = list(csv.DictReader((run_dir / "order/order-ranking-production.csv").open(encoding="utf-8")))
    assert production
    assert production[0]["production_eligible"] == "True"

    master = (run_dir / "TEST2-COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    assert "PROMPT-SENTINEL" in master
    assert "RESPONSE-SENTINEL" in master
    assert "NEXT-STRIDE-SENTINEL" in master
    assert "FAIL_TO_SUCCESS" in master
    assert "order/order-ranking-production.csv" in master


def test_test2_writer_hash_inventory_is_complete_and_deterministically_sorted(tmp_path):
    run_dir = tmp_path / "test2"
    Test2ArtifactWriter(run_dir).write_all(_minimal_evidence())
    rows = list(csv.DictReader((run_dir / "SHA256SUMS.csv").open(encoding="utf-8")))
    paths = [row["path"] for row in rows]
    assert paths == sorted(paths)
    assert "TEST2-COMPLETE-EVIDENCE.txt" in paths
    assert "order/order-ranking-production.csv" in paths
    assert all(len(row["sha256"]) == 64 for row in rows)
    json.loads((run_dir / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))