from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.harvest_d.d3_closure_r1_cli import _validate_historical_gap_registry


def test_r1_accepts_actual_post_d3_gap_registry_array(tmp_path: Path):
    path = tmp_path / "post_d3_gap_registry.json"
    path.write_text(json.dumps([
        {"gap_id": "GAP-QWEN-DELIBERATION", "class": "MEASUREMENT_OR_ORACLE_RISK", "destination": "D4"},
        {"gap_id": "GAP-MINIMUM-SUPPORT", "class": "MINIMUM_SUPPORT_UNKNOWN", "destination": "D3-CLOSURE-v2"},
    ]), encoding="utf-8")
    rows = _validate_historical_gap_registry(path)
    assert len(rows) == 2
    assert all(row["gap_id"].startswith("GAP-") for row in rows)


def test_r1_rejects_empty_or_malformed_historical_gap_registry(tmp_path: Path):
    for payload in ([], {}, ["bad"]):
        path = tmp_path / "post_d3_gap_registry.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            _validate_historical_gap_registry(path)
