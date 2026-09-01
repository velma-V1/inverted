import csv
import hashlib
import json
from pathlib import Path

from inverted.models import MockModelAdapter
from inverted.test3_s2_analysis import derive_s2_verdict, summarize_s2
from inverted.test3_s2_artifacts import REQUIRED_S2_FILES, Test3S2ArtifactWriter
from inverted.test3_s2_cases import build_holdout_b
from inverted.test3_s2_runtime import run_s2_screen


def _models():
    return {
        "qwen3.5:9b-q8_0": MockModelAdapter("qwen3.5:9b-q8_0"),
        "cogito:3b-v1-preview-llama-q8_0": MockModelAdapter("cogito:3b-v1-preview-llama-q8_0"),
        "llama3.1:8b": MockModelAdapter("llama3.1:8b"),
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s2_writer_emits_complete_hash_verified_forensic_packet(tmp_path):
    runtime = run_s2_screen(cases=build_holdout_b(), model_by_name=_models(), run_id="artifact-mock")
    analysis = summarize_s2(runtime)
    verdict = derive_s2_verdict(analysis)
    evidence = {
        **runtime,
        **analysis,
        "verdict": verdict,
        "preregistration": {"protocol_revision": "S2-R1", "holdout": "B-R1", "exact_budget": 720},
        "config": {"s2": {"hard_call_limit": 720}},
        "provenance": {"run_id": "artifact-mock", "protocol_revision": "S2-R1", "execution_holdout": "B-R1"},
        "router_policy_snapshot": {"arms": ["S2-B0", "S2-B1", "S2-B2", "S2-B3", "S2-B4"]},
        "router_policy_hashes": [{"arm_id": "S2-B3", "sha256": "abc"}],
        "edge_cases": [],
        "instrumentation_anomalies": list(runtime["stochastic_divergence"]),
        "report": "S2 mock report\n",
    }
    written = Test3S2ArtifactWriter(tmp_path).write_all(evidence)

    assert set(REQUIRED_S2_FILES).issubset(set(written))
    assert all((tmp_path / name).is_file() for name in REQUIRED_S2_FILES)

    master = json.loads((tmp_path / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    assert master["experiment"] == "test3-section2-adaptive-routing"
    assert master["protocol_revision"] == "S2-R1"
    assert master["holdout"] == "B-R1"
    assert master["physical_model_calls"] == 720
    assert master["combined_external_actions"] == 720
    assert master["trial_rows"] == 360
    assert master["matched_case_count"] == 72

    complete = (tmp_path / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    for name in REQUIRED_S2_FILES:
        if name not in {"SHA256SUMS.csv", "COMPLETE-EVIDENCE.txt"}:
            assert f"BEGIN FILE: {name}" in complete

    with (tmp_path / "SHA256SUMS.csv").open(encoding="utf-8", newline="") as handle:
        inventory = list(csv.DictReader(handle))
    indexed = {row["path"]: row for row in inventory}
    for name in REQUIRED_S2_FILES:
        if name == "SHA256SUMS.csv":
            continue
        assert name in indexed
        assert indexed[name]["sha256"] == _sha(tmp_path / name)
        assert int(indexed[name]["bytes"]) == (tmp_path / name).stat().st_size
