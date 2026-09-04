import json
from pathlib import Path

import pytest

from inverted.harvest_d.post_d3_analysis import analyze_d3_v1


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_post_d3_analysis_is_read_only_and_writes_required_outputs(tmp_path: Path):
    root = tmp_path / "d3-v1"
    out = tmp_path / "post"
    root.mkdir()
    _write_jsonl(
        root / "d3_normalized_model_calls.jsonl",
        [
            {
                "model_id": "qwen3.5:9b-q8_0",
                "failure_class": "BOTH_WRONG",
                "score": {"answer_correct": True, "disposition_correct": False},
                "input_tokens": 100,
                "output_tokens": 3996,
                "runtime_extras": {},
            },
            {
                "model_id": "qwen2.5:1.5b-instruct-q8_0",
                "failure_class": "ANSWER_RIGHT_DISPOSITION_WRONG",
                "score": {"answer_correct": True, "disposition_correct": False},
                "input_tokens": 120,
                "output_tokens": 20,
                "runtime_extras": {},
            },
        ],
    )
    _write_jsonl(
        root / "d3_runtime_telemetry.jsonl",
        [
            {"model": "qwen3.5:9b-q8_0", "done_reason": "length", "prompt_eval_count": 100, "eval_count": 3996},
            {"model": "qwen2.5:1.5b-instruct-q8_0", "done_reason": "stop", "prompt_eval_count": 120, "eval_count": 20},
        ],
    )
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

    result = analyze_d3_v1(root, out)

    required = {
        "post_d3_gap_registry.json",
        "post_d3_zero_call_findings.json",
        "post_d3_decision_impact_map.json",
        "post_d3_hypothesis_lineage.json",
        "post_d3_followup_routing.json",
        "post_d3_followup_test_spec.md",
        "post_d3_followup_budget_justification.json",
    }
    assert required <= {p.name for p in out.iterdir()}
    assert result["protocol"] == "D3-V1-POSTHOC-SALVAGE"
    assert result["physical_calls_observed"] == 2
    assert result["disposition_correct_calls"] == 0
    assert result["qwen_context_exhausted"] == 1
    assert "d3_recovery_trajectories.jsonl" in result["empty_required_artifacts"]
    assert all(p.is_file() for p in root.iterdir())


def test_post_d3_analysis_refuses_to_write_into_frozen_input(tmp_path: Path):
    root = tmp_path / "d3-v1"
    root.mkdir()
    with pytest.raises(ValueError):
        analyze_d3_v1(root, root)
