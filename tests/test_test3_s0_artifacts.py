from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from inverted.test3_s0_artifacts import REQUIRED_PACKET_FILES, Test3S0ArtifactWriter


def _minimal_evidence():
    return {
        "preregistration": {"status": "CANDIDATE_ONLY_NOT_PREREGISTERED"},
        "config": {"physical_model_call_ceiling": 0},
        "provenance": {"git_sha": "abc"},
        "model_calls": [],
        "events": [{"event": "normalization", "metadata": {"edge": "preserved"}}],
        "trials": [{"task_id": "t1", "success": True}],
        "validator_results": [{"task_id": "t1", "verifier": "det", "result": "pass"}],
        "failures": [{"task_id": "t2", "failure_class": "instrumentation"}],
        "wins": [{"task_id": "t1"}],
        "losses": [{"task_id": "t2"}],
        "transitions": [{"transition_id": "x", "metadata": {"unknown_field": 7}}],
        "counterfactuals": [{"counterfactual_id": "c1", "status": "CAUSAL_REPLAY"}],
        "costs": [{"task_id": "t1", "physical_calls": 0}],
        "latency": [{"task_id": "t1", "elapsed_ms": 1.5}],
        "tokens": [{"task_id": "t1", "tokens": None}],
        "cache": [{"task_id": "t1", "cache_hit": False}],
        "failure_atlas": {"classes": {"instrumentation": 1}},
        "effect_sizes": {"candidate": 0.1},
        "verdict": {"verdict": "DISCOVERY_COMPLETE_MODEL_FREE"},
        "source_manifest": {"sources": []},
        "source_integrity": [],
        "normalization_coverage": [],
        "normalization_errors": [{"line": 2, "error": "bad json", "raw": "{bad}"}],
        "fixed_policy_candidates": [],
        "adaptive_policy_candidates": [],
        "control_results": [],
        "pareto_frontier": [],
        "unresolved_causal_questions": [],
        "requires_new_inference": [],
        "invalid_counterfactuals": [],
        "power_variance": {"status": "INSUFFICIENT_VARIANCE_EVIDENCE"},
        "candidate_section1_preregistration": {"exact_budget": None},
        "instrumentation_anomalies": [{"kind": "normalization_error"}],
        "unknown_fields": [{"field": "mystery"}],
        "comparison_evidence": [{"source_file": "effects/component.csv", "delta": 0.125}],
        "source_metadata": [{"source_id": "s1", "source_file": "provenance.json", "value": {"rare": {"x": 7}}}],
        "data_quality": {},
        "report": "S0 report\n",
    }


def test_writer_emits_complete_packet_and_preserves_edge_metadata(tmp_path: Path):
    writer = Test3S0ArtifactWriter(tmp_path)
    writer.write_all(_minimal_evidence())
    missing = [name for name in REQUIRED_PACKET_FILES if not (tmp_path / name).exists()]
    assert missing == []
    with (tmp_path / "transitions.csv").open(encoding="utf-8", newline="") as handle:
        transition_rows = list(csv.DictReader(handle))
    assert json.loads(transition_rows[0]["metadata"])["unknown_field"] == 7
    assert "{bad}" in (tmp_path / "normalization_errors.csv").read_text(encoding="utf-8")


def test_writer_derives_data_quality_when_caller_supplies_empty_placeholder(tmp_path: Path):
    writer = Test3S0ArtifactWriter(tmp_path)
    writer.write_all(_minimal_evidence())
    quality = json.loads((tmp_path / "data_quality.json").read_text(encoding="utf-8"))
    assert quality["normalization_errors"] == 1
    assert quality["instrumentation_anomalies"] == 1
    assert quality["unknown_field_records"] == 1
    assert quality["zero_model_call_invariant"] is True
    assert "never silently coerce" in quality["data_loss_policy"]


def test_writer_emits_full_comparison_and_source_metadata_evidence(tmp_path: Path):
    writer = Test3S0ArtifactWriter(tmp_path)
    writer.write_all(_minimal_evidence())
    comparison_path = tmp_path / "comparison_evidence.csv"
    metadata_path = tmp_path / "source_metadata.jsonl"
    assert comparison_path.exists()
    assert metadata_path.exists()
    with comparison_path.open(encoding="utf-8", newline="") as handle:
        comparisons = list(csv.DictReader(handle))
    assert float(comparisons[0]["delta"]) == 0.125
    metadata_row = json.loads(metadata_path.read_text(encoding="utf-8").splitlines()[0])
    assert metadata_row["value"]["rare"]["x"] == 7


def test_sha_inventory_matches_written_files(tmp_path: Path):
    writer = Test3S0ArtifactWriter(tmp_path)
    writer.write_all(_minimal_evidence())
    with (tmp_path / "SHA256SUMS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        path = tmp_path / row["path"]
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_complete_evidence_contains_every_textual_packet_before_hash_inventory(tmp_path: Path):
    writer = Test3S0ArtifactWriter(tmp_path)
    writer.write_all(_minimal_evidence())
    master = (tmp_path / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    assert "BEGIN FILE: transitions.csv" in master
    assert "BEGIN FILE: normalization_errors.csv" in master
    assert "BEGIN FILE: comparison_evidence.csv" in master
    assert "BEGIN FILE: source_metadata.jsonl" in master
    assert "BEGIN FILE: verdict.json" in master
