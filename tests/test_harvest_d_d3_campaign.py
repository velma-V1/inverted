from io import StringIO
import json

import pytest

from inverted.harvest_d.d3_campaign import D3Campaign
from inverted.harvest_d.models import ModelResponse


class SequenceAdapter:
    model_id = "fake:d3"

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        index = min(self.calls, len(self.payloads) - 1)
        payload = self.payloads[index]
        self.calls += 1
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return ModelResponse(text, self.model_id, 5, 5, 10.0, {"message": {"content": text}})


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
