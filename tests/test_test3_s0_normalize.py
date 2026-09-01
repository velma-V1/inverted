from __future__ import annotations

import json
from pathlib import Path

from inverted.test3_s0_normalize import (
    normalize_bundle,
    normalize_test2_event,
)


def test_model_free_event_normalizes_without_inventing_model_fields():
    row = {
        "case_id": "mf-state-L1-q0.20-s1001-e0",
        "family": "state",
        "complexity": 1,
        "component": "retry",
        "step": 2,
        "before_success": False,
        "before_blocked": True,
        "after_success": False,
        "after_blocked": False,
        "transition": "FAIL_TO_DIFFERENT_FAIL",
        "candidate_index": 1,
    }
    out = normalize_test2_event("test2-mf", row)
    assert out.state_before.task_id == row["case_id"]
    assert out.state_before.task_family == "state"
    assert out.action.component == "retry"
    assert out.action.model is None
    assert out.state_before.semantic_result is None
    assert out.state_before.tokens_spent is None
    assert out.state_after.blocked is False
    assert out.transition_index == 2
    assert out.raw_record_hash


def test_normalization_attaches_temporal_provenance_to_state_features():
    row = {
        "case_id": "x",
        "family": "tool",
        "component": "validator",
        "step": 4,
        "failure_signature": "SCHEMA_MISMATCH",
        "before_success": False,
        "after_success": True,
    }
    out = normalize_test2_event("source", row)
    provenance = {p.feature_name: p for p in out.state_before.feature_provenance}
    assert provenance["failure_signature"].available_before_action is True
    assert provenance["failure_signature"].derived_at_transition == 4


def test_malformed_jsonl_is_retained_as_normalization_error(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "events.jsonl").write_text('{"case_id":"ok","component":"retry"}\n{bad-json}\n', encoding="utf-8")
    result = normalize_bundle("s", "test2_model_free", bundle)
    assert len(result.transitions) == 1
    assert len(result.errors) == 1
    assert result.errors[0]["record_type"] == "events.jsonl"
    assert result.coverage[0]["input_rows"] == 2
    assert result.coverage[0]["dropped_rows"] == 1
