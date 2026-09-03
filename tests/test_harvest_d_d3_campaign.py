from io import StringIO
import json

import pytest

from inverted.harvest_d.d3_campaign import D3Campaign
from inverted.harvest_d.d3_cases import generate_d3_cases
from inverted.harvest_d.d3_planner import D3ExperimentPlanner
from inverted.harvest_d.d3_scheduler import D3Scheduler
from inverted.harvest_d.models import ModelResponse


class SequenceAdapter:
    model_id = "fake:d3"

    def __init__(self, payloads, *, model_id: str | None = None):
        self.payloads = list(payloads)
        self.calls = 0
        self.prompts: list[str] = []
        self.systems: list[str | None] = []
        if model_id is not None:
            self.model_id = model_id

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        index = min(self.calls, len(self.payloads) - 1)
        payload = self.payloads[index]
        self.calls += 1
        self.prompts.append(prompt)
        self.systems.append(system)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return ModelResponse(text, self.model_id, 5, 5, 10.0, {"message": {"content": text}})


def _planner(model_keys=("SMALL_A", "QWEN")):
    return D3ExperimentPlanner(
        development_cases=generate_d3_cases(partition="development", seed=20260903, per_family=1),
        fresh_cases=generate_d3_cases(partition="fresh", seed=20260913, per_family=1),
        sealed_cases=generate_d3_cases(partition="sealed", seed=20261003, per_family=1),
        model_keys=tuple(model_keys),
    )


def test_campaign_runs_unattended_until_configured_evidence_ceiling(tmp_path):
    adapter = SequenceAdapter([{"answer": "ok", "hard_invariant_ok": True}])
    progress = StringIO()
    campaign = D3Campaign.testing(tmp_path, adapter=adapter, max_calls=12, progress_stream=progress)
    result = campaign.run()
    assert result.calls_used == 12
    assert adapter.calls == 12
    assert result.operator_actions_required == ()
    assert result.final_state == "EVIDENCE_CEILING_REACHED"
    assert "%" in progress.getvalue()
    assert "12/12" in progress.getvalue()


def test_production_campaign_uses_planner_cases_and_routes_calls_to_declared_models(tmp_path):
    small = SequenceAdapter([{"disposition": "EXECUTE", "answer": "USE_CURRENT"}], model_id="fake:small")
    qwen = SequenceAdapter([{"disposition": "EXECUTE", "answer": "USE_CURRENT"}], model_id="fake:qwen")
    planner = _planner()
    campaign = D3Campaign.production(
        tmp_path,
        adapters={"SMALL_A": small, "QWEN": qwen},
        planner=planner,
        max_calls=30,
        progress_stream=StringIO(),
        scheduler=D3Scheduler.default(random_stream_fraction=0.0),
    )
    result = campaign.run()
    assert result.calls_used == 30
    assert small.calls > 0
    assert qwen.calls > 0
    assert small.calls + qwen.calls == 30
    assert all("Return one JSON object describing your proposed D3 decision" not in p for p in (*small.prompts, *qwen.prompts))
    assert all("D3 controlled decision case" in p for p in (*small.prompts, *qwen.prompts))


def test_production_campaign_writes_zero_call_assistance_replays_without_extra_model_calls(tmp_path):
    adapter = SequenceAdapter([{"disposition": "EXECUTE", "answer": "USE_CURRENT"}], model_id="fake:small")
    planner = _planner(("SMALL_A",))
    campaign = D3Campaign.production(
        tmp_path,
        adapters={"SMALL_A": adapter},
        planner=planner,
        max_calls=67,
        progress_stream=StringIO(),
        scheduler=D3Scheduler.default(random_stream_fraction=0.0),
    )
    result = campaign.run()
    assert result.calls_used == 67
    assert adapter.calls == 67
    replay_lines = (tmp_path / "d3_counterfactuals.jsonl").read_text(encoding="utf-8").splitlines()
    assert replay_lines
    rows = [json.loads(line) for line in replay_lines]
    assert all(row["physical_model_calls_used"] == 0 for row in rows)
    assert {row["mode"] for row in rows} == {"OFF", "TARGET", "SHAM"}


def test_hard_invariant_violation_halts_before_another_model_call(tmp_path):
    adapter = SequenceAdapter([
        {"answer": "ok", "hard_invariant_ok": True},
        {"answer": "unsafe", "hard_invariant_ok": False},
        {"answer": "should-not-run", "hard_invariant_ok": True},
    ])
    result = D3Campaign.testing(tmp_path, adapter=adapter, max_calls=10, progress_stream=StringIO()).run()
    assert result.final_state == "HARD_STOP"
    assert result.hard_stop_reason == "HARD_INVARIANT_VIOLATION"
    assert adapter.calls == 2
    assert result.calls_used == 2


def test_malformed_model_output_is_evidence_not_campaign_stop(tmp_path):
    adapter = SequenceAdapter(["not json"])
    result = D3Campaign.testing(tmp_path, adapter=adapter, max_calls=3, progress_stream=StringIO()).run()
    assert adapter.calls == 3
    assert result.final_state == "EVIDENCE_CEILING_REACHED"


def test_campaign_rejects_call_ceiling_above_d3_absolute_limit(tmp_path):
    adapter = SequenceAdapter([{"hard_invariant_ok": True}])
    with pytest.raises(ValueError):
        D3Campaign.testing(tmp_path, adapter=adapter, max_calls=1001)


def test_model_free_preflight_never_calls_adapter(tmp_path):
    adapter = SequenceAdapter([{"hard_invariant_ok": True}])
    campaign = D3Campaign.testing(tmp_path, adapter=adapter, max_calls=5, progress_stream=StringIO())
    result = campaign.preflight(model_free=True)
    assert result.calls_used == 0
    assert result.oracle_leakage_check is True
    assert adapter.calls == 0
