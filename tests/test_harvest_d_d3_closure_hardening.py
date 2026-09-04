import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from inverted.harvest_d.d3_closure_campaign import D3ClosureCampaign
from inverted.harvest_d.d3_closure_cli import load_closure_config
from inverted.harvest_d.d3_closure_scoring import SystemSemantics, compile_system_disposition
from inverted.harvest_d.models import ModelResponse
from inverted.harvest_d.post_d3_analysis import analyze_d3_v1
from inverted.harvest_d.types import Disposition


CONFIG = Path("configs/harvest-d-d3-closure-v2.json")


class _WrongAdapter:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.calls = 0
        self.generation_options = {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096}
        self.chat_options = {}

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            '{"answer":"NOT_THE_ORACLE"}',
            self.model_id,
            100,
            20,
            1.0,
            {"done_reason": "stop", "prompt_eval_count": 100, "eval_count": 20},
        )


def test_final_system_disposition_enforces_authority_boundary():
    assert compile_system_disposition(
        SystemSemantics(authority_allows=False)
    ) is Disposition.ESCALATE


def test_full_closure_executes_complete_fixed_core_and_emits_recovery_analysis(tmp_path: Path):
    config = load_closure_config(CONFIG)
    small = _WrongAdapter(config["models"]["SMALL_A"])
    qwen = _WrongAdapter(config["models"]["QWEN"])
    campaign = D3ClosureCampaign(
        tmp_path,
        config=config,
        adapters={"SMALL_A": small, "QWEN": qwen},
        progress_stream=io.StringIO(),
    )
    result = campaign.run()
    assert result.physical_model_calls == campaign.plan.planned_physical_calls
    assert small.calls + qwen.calls == campaign.plan.planned_physical_calls

    trajectories = [
        json.loads(line)
        for line in (tmp_path / "closure_recovery_trajectories.jsonl").read_text().splitlines()
        if line.strip()
    ]
    planned_c4 = len([row for row in campaign.plan.experiments if row.block == "C4"])
    assert len(trajectories) == planned_c4

    recovery_map = json.loads((tmp_path / "closure_recovery_policy_map.json").read_text())
    assert recovery_map["trajectory_count"] == planned_c4
    report = json.loads((tmp_path / "closure_final_report.json").read_text())
    assert report["scientific_complete"] is True
    assert report["completed_experiments"] == campaign.plan.planned_physical_calls
    assert report["missing_experiments"] == 0


def test_closure_resume_refuses_ambiguous_started_physical_call(tmp_path: Path):
    config = load_closure_config(CONFIG)
    small = _WrongAdapter(config["models"]["SMALL_A"])
    qwen = _WrongAdapter(config["models"]["QWEN"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "closure_campaign_journal.jsonl").write_text(
        json.dumps({
            "physical_model_call_id": "ambiguous-call",
            "experiment_id": "C1:SMALL_A:ambiguous:RAW",
            "state": "STARTED",
        }) + "\n",
        encoding="utf-8",
    )
    campaign = D3ClosureCampaign(
        tmp_path,
        config=config,
        adapters={"SMALL_A": small, "QWEN": qwen},
        progress_stream=io.StringIO(),
    )
    with pytest.raises(ValueError, match="ambiguous"):
        campaign.run(max_calls=1)
    assert small.calls + qwen.calls == 0


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_minimal_valid_d3(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_jsonl(root / "d3_normalized_model_calls.jsonl", [{
        "physical_model_call_id": "call-1",
        "model_id": "qwen3.5:9b-q8_0",
        "score": {"answer_correct": True, "disposition_correct": False},
    }])
    _write_jsonl(root / "d3_runtime_telemetry.jsonl", [{
        "physical_model_call_id": "call-1",
        "model": "qwen3.5:9b-q8_0",
        "done_reason": "length",
        "prompt_eval_count": 100,
        "eval_count": 3996,
    }])
    _write_jsonl(root / "d3_call_ledger.jsonl", [{
        "physical_model_call_id": "call-1",
        "capture_complete": True,
        "admissibility": "ADMISSIBLE",
    }])
    (root / "00-HARVEST-D-D3-MASTER-INDEX.json").write_text(json.dumps({
        "mode": "REAL_LOCAL",
        "physical_model_calls": 1,
        "audit_passed": True,
        "empirical_claims_authorized": True,
    }) + "\n", encoding="utf-8")
    (root / "d3_final_report.json").write_text(json.dumps({
        "mode": "REAL_LOCAL",
        "physical_model_calls": 1,
        "audit_passed": True,
        "empirical_claims_authorized": True,
    }) + "\n", encoding="utf-8")
    for name in (
        "d3_causal_claim_graph.jsonl",
        "d3_claim_evidence_edges.jsonl",
        "d3_decision_boundary_telemetry.jsonl",
        "d3_evidence_saturation.jsonl",
        "d3_model_behavior_features.jsonl",
        "d3_recovery_trajectories.jsonl",
        "d3_sequential_analysis_state.jsonl",
        "d3_uncovered_space.jsonl",
    ):
        (root / name).write_text("", encoding="utf-8")

    rows = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name == "SHA256SUMS.csv":
            continue
        payload = path.read_bytes()
        rows.append({"file": path.name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    with (root / "SHA256SUMS.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("file", "bytes", "sha256"))
        writer.writeheader()
        writer.writerows(rows)


def test_post_d3_analysis_rejects_incomplete_frozen_source(tmp_path: Path):
    root = tmp_path / "d3"
    root.mkdir()
    with pytest.raises(ValueError, match="frozen D3-v1"):
        analyze_d3_v1(root, tmp_path / "post")


def test_post_d3_analysis_verifies_frozen_source_checksums(tmp_path: Path):
    root = tmp_path / "d3"
    _write_minimal_valid_d3(root)
    with (root / "d3_normalized_model_calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"physical_model_call_id": "tamper"}) + "\n")
    with pytest.raises(ValueError, match="checksum"):
        analyze_d3_v1(root, tmp_path / "post")
