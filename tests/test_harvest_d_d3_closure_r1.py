from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.harvest_d.d3_closure_r1 import (
    R1_MAX_CALLS,
    build_r1_plan,
    build_r1_model_free_package,
    validate_r1_stage_authorization,
)


def _config() -> dict:
    return {
        "schema_version": 1,
        "protocol": "D3-CLOSURE-v2",
        "max_calls": 200,
        "sealed_reserve": 48,
        "ollama_base_url": "http://127.0.0.1:11434",
        "models": {"SMALL_A": "small:test", "QWEN": "qwen:test"},
        "generation_options": {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096},
        "seeds": {"development": 20261103, "fresh": 20261113, "sealed": 20261203},
        "cases_per_family": {"development": 2, "fresh": 1, "sealed": 1},
        "d4_policy": {"policy_id": "PENDING_D4", "chat_options": {}},
        "blind_retries_allowed": False,
    }


def test_r1_plan_is_exactly_bounded_and_repeated():
    plan = build_r1_plan(_config())
    assert R1_MAX_CALLS == 24
    assert plan.max_calls == 24
    assert len(plan.experiments) == 24
    assert {row.model_key for row in plan.experiments} == {"SMALL_A", "QWEN"}
    assert len({row.case_id for row in plan.experiments}) == 3
    for model_key in ("SMALL_A", "QWEN"):
        for case_id in {row.case_id for row in plan.experiments}:
            matched = [row for row in plan.experiments if row.model_key == model_key and row.case_id == case_id]
            assert len(matched) == 4
            assert {row.repeat_index for row in matched} == {1, 2, 3, 4}


def test_r1_plan_intersperses_sentinal_and_never_names_legacy_blocks():
    plan = build_r1_plan(_config())
    sentinel_positions = [index for index, row in enumerate(plan.experiments) if row.sentinel]
    assert len(sentinel_positions) >= 4
    assert max(sentinel_positions) - min(sentinel_positions) >= 12
    assert all(row.stage == "R1_CALIBRATION" for row in plan.experiments)
    assert not ({"C1", "C2", "C3", "C4", "C5", "C6", "C7"} & {row.stage for row in plan.experiments})


def test_r1_model_free_package_is_zero_call_and_not_test5_ready(tmp_path: Path):
    summary = build_r1_model_free_package(tmp_path, _config())
    assert summary["physical_model_calls"] == 0
    assert summary["stage"] == "R1_CALIBRATION"
    assert summary["final_state"] == "R1_MODEL_FREE_COMPLETE"
    assert summary["max_physical_calls"] == 24
    assert summary["ready_for_physical_r1"] is False
    assert summary["ready_for_test5"] is False
    required = {
        "closure_r1_plan.json",
        "closure_r1_readiness.json",
        "closure_reproducibility_calibration.json",
        "closure_cost_calibration.json",
        "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json",
        "SHA256SUMS.csv",
    }
    assert required <= {path.name for path in tmp_path.iterdir() if path.is_file()}
    repro = json.loads((tmp_path / "closure_reproducibility_calibration.json").read_text())
    cost = json.loads((tmp_path / "closure_cost_calibration.json").read_text())
    assert repro["state"] == "NOT_RUN"
    assert cost["state"] == "NOT_RUN"


def test_r1_stage_authorization_is_narrow_and_fails_closed():
    good = {
        "schema_version": 1,
        "protocol": "D3-CLOSURE-v2",
        "stage": "R1_CALIBRATION",
        "stage_physical_execution_authorized": True,
        "max_physical_calls": 24,
        "legacy_closure_physical_execution_authorized": False,
    }
    validate_r1_stage_authorization(good)

    for patch in (
        {"stage": "CLOSURE"},
        {"max_physical_calls": 25},
        {"legacy_closure_physical_execution_authorized": True},
        {"stage_physical_execution_authorized": False},
    ):
        bad = dict(good)
        bad.update(patch)
        with pytest.raises(ValueError):
            validate_r1_stage_authorization(bad)
