from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.harvest_d.d3_closure_r1 import R1CalibrationCampaign, build_r1_plan
from inverted.harvest_d.models import ModelResponse


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


class _Adapter:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.calls = 0

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        return ModelResponse('{"answer":"x"}', self.model_id, 1, 1, 1.0, {"done_reason": "stop"})


def test_r1_resume_refuses_ambiguous_started_but_uncommitted_call(tmp_path: Path):
    config = _config()
    first = build_r1_plan(config).experiments[0]
    (tmp_path / "closure_r1_campaign_journal.jsonl").write_text(
        json.dumps({"experiment_id": first.experiment_id, "state": "STARTED", "attempt": 1}) + "\n",
        encoding="utf-8",
    )
    small = _Adapter("small:test")
    qwen = _Adapter("qwen:test")
    campaign = R1CalibrationCampaign(
        tmp_path,
        config=config,
        adapters={"SMALL_A": small, "QWEN": qwen},
        runtime_identity={
            "SMALL_A": {"model_id": "small:test", "model_digest": "small-digest", "installed_size_gib": 1.0},
            "QWEN": {"model_id": "qwen:test", "model_digest": "qwen-digest", "installed_size_gib": 9.4},
        },
    )
    with pytest.raises(ValueError, match="ambiguous"):
        campaign.run(max_calls=1)
    assert small.calls + qwen.calls == 0
