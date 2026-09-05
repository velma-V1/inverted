from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.harvest_d.hd_next1_authorization import authorize_hd_next1_execution
from inverted.harvest_d.hd_next1_campaign import HDNext1Campaign
from inverted.harvest_d.hd_next1_config import load_hd_next1_config
from inverted.harvest_d.hd_next1_preregistration import build_preregistration_package


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "harvest-d-hd-next-1.json"


class FailingAdapter:
    model_id = "synthetic-test-model"
    generation_options = {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096}

    def __init__(self):
        self.calls = 0

    def complete(self, prompt: str, system: str | None = None):
        self.calls += 1
        raise RuntimeError("synthetic adapter failure")


def test_live_campaign_refuses_without_owner_authorization(tmp_path):
    cfg = load_hd_next1_config(CONFIG)
    build_preregistration_package(REPO, tmp_path / "prereg", cfg)
    campaign = HDNext1Campaign(tmp_path / "run", prereg_root=tmp_path / "prereg", config=cfg, adapters={"SMALL_A": FailingAdapter(), "QWEN": FailingAdapter()})
    with pytest.raises(ValueError, match="owner"):
        campaign.run_authorized(max_calls=1)


def test_authorized_campaign_attempts_each_assignment_once_without_retry(tmp_path):
    cfg = load_hd_next1_config(CONFIG)
    prereg = tmp_path / "prereg"
    build_preregistration_package(REPO, prereg, cfg)
    owner = authorize_hd_next1_execution(prereg, owner_approved=True)
    adapter = FailingAdapter()
    campaign = HDNext1Campaign(tmp_path / "run", prereg_root=prereg, config=cfg, adapters={"SMALL_A": adapter, "QWEN": adapter}, owner_authorization=owner)
    result = campaign.run_authorized(max_calls=1)
    assert result.physical_model_calls == 1
    assert adapter.calls == 1
    rows = [json.loads(line) for line in (tmp_path / "run" / "physical_call_ledger.jsonl").read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["attempt"] == 1
    assert rows[0]["automatic_retry"] is False
