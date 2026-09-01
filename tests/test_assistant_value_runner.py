import json
from pathlib import Path

import pytest

from inverted.models import MockModelAdapter
from inverted.assistant_value.runner import run_assistant_value_test


def _smoke_config():
    return {
        "assistant_value": {
            "capture_content": True,
            "seed": 20260901,
            "long_horizon": {
                "call_cap": 1152,
                "per_horizon": 1,
                "horizons": [2],
                "arms": ["DIRECT", "CHECKED", "INVERTED"],
            },
            "evidence_trust": {
                "call_cap": 1080,
                "cases_per_regime": 1,
                "arms": ["DIRECT", "CHECKED", "INVERTED"],
            },
            "authority": {
                "call_cap": 1152,
                "cases_per_class": 1,
                "arms": ["DIRECT", "CHECKED", "INVERTED"],
            },
            "ground_truth_isolation": {
                "call_cap": 1080,
                "cases_per_regime": 1,
                "arms": ["DIRECT", "CHECKED", "INVERTED"],
            },
        }
    }


@pytest.mark.parametrize("test_name", ["long_horizon", "evidence_trust", "authority", "ground_truth_isolation"])
def test_mock_smoke_run_writes_complete_lossless_packet(tmp_path, test_name):
    model = MockModelAdapter(model="mock-rule", seed=7, capture_content=True)
    result = run_assistant_value_test(
        test_name,
        _smoke_config(),
        [model],
        tmp_path,
        run_id=f"smoke-{test_name}",
    )
    root = Path(result["root"])
    integrity = json.loads((root / "integrity.json").read_text(encoding="utf-8"))
    budget = json.loads((root / "budget.json").read_text(encoding="utf-8"))

    assert integrity["status"] == "OK"
    assert integrity["budget_violation"] is False
    assert budget["used"] == result["budget"]["used"]
    assert budget["used"] <= budget["cap"]

    calls = [line for line in (root / "model_calls.jsonl").read_text(encoding="utf-8").splitlines() if line]
    prompts = [line for line in (root / "prompts.jsonl").read_text(encoding="utf-8").splitlines() if line]
    responses = [line for line in (root / "responses.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert len(calls) == budget["used"]
    assert len(prompts) == budget["used"]
    assert len(responses) == budget["used"]
    assert (root / "COMPLETE-EVIDENCE.txt").stat().st_size > 0


def test_runner_refuses_over_budget_plan_before_first_model_call(tmp_path):
    config = _smoke_config()
    config["assistant_value"]["evidence_trust"]["cases_per_regime"] = 100
    model = MockModelAdapter(model="mock-rule", seed=7, capture_content=True)

    with pytest.raises(ValueError, match="planned physical model calls"):
        run_assistant_value_test(
            "evidence_trust",
            config,
            [model],
            tmp_path,
            run_id="over-budget",
        )
