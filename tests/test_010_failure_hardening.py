import json

import httpx
import pytest

from inverted.cli import _build_models
from inverted.models import ModelCallError, OllamaAdapter
from inverted.runner import ExperimentConfig, build_trial_plan


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request, json=self._payload)
            raise httpx.HTTPStatusError("provider error", request=self.request, response=response)

    def json(self):
        return self._payload


def _ctx():
    return {"run_id": "r", "trial_id": "t", "call_id": "c"}


def test_ollama_retries_transient_no_response_and_records_recovery(monkeypatch):
    attempts = []

    def fake_post(url, *, json, timeout):
        attempts.append((url, json, timeout))
        if len(attempts) < 3:
            raise httpx.ReadTimeout("no model response", request=httpx.Request("POST", url))
        return _Response(payload={
            "message": {"content": '{"accept":true}'},
            "done_reason": "stop",
            "prompt_eval_count": 12,
            "eval_count": 4,
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(
        model="qwen",
        timeout_s=600,
        max_retries=2,
        retry_backoff_s=0,
        think=False,
        format_json=True,
        context_limit=8192,
    )
    result = model.complete([{"role": "user", "content": "x"}], role="auditor", context=_ctx())

    assert len(attempts) == 3
    assert result.record.retry_number == 2
    assert len(result.record.raw_provider_telemetry["retry_errors"]) == 2
    payload = attempts[-1][1]
    assert payload["think"] is False
    assert payload["format"] == "json"
    assert payload["options"]["num_ctx"] == 8192


def test_ollama_retries_empty_200_response_instead_of_scoring_it(monkeypatch):
    calls = 0

    def fake_post(url, *, json, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _Response(payload={"message": {"content": ""}, "done_reason": "length", "eval_count": 1024})
        return _Response(payload={"message": {"content": '{"actions":[]}'}, "done_reason": "stop", "eval_count": 5})

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="qwen", max_retries=2, retry_backoff_s=0, think=False, format_json=True)
    result = model.complete([{"role": "user", "content": "x"}], role="executor", context=_ctx())
    assert calls == 2
    assert result.record.retry_number == 1
    assert result.record.raw_provider_telemetry["retry_errors"][0]["error_class"] == "EmptyModelResponse"


def test_ollama_exhausted_transport_failure_aborts_instead_of_returning_scored_failure(monkeypatch):
    def fake_post(url, *, json, timeout):
        raise httpx.ReadTimeout("stalled", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="qwen", max_retries=2, retry_backoff_s=0)
    with pytest.raises(ModelCallError) as excinfo:
        model.complete([{"role": "user", "content": "x"}], role="executor", context=_ctx())
    assert excinfo.value.record.retry_number == 2
    assert excinfo.value.record.timeout is True


def test_decisive_ollama_models_have_frozen_reliability_contract():
    raw = {
        "models": [{
            "provider": "ollama",
            "model": "m",
            "timeout_s": 600,
            "max_retries": 2,
            "retry_backoff_s": 5,
            "think": False,
            "format_json": True,
            "context_limit": 8192,
        }]
    }
    model = _build_models(raw, capture_content=True)[0]
    assert model.timeout_s == 600
    assert model.max_retries == 2
    assert model.think is False
    assert model.format_json is True
    assert model.context_limit == 8192


def test_model_dependent_plan_is_grouped_by_model_to_avoid_ollama_swap_thrash():
    models = [type("M", (), {"provider": "ollama", "model": name})() for name in ("q", "g", "d")]
    cfg = ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.2, 0.8), seeds=(1, 2), epochs=1,
        arms=("A_DIRECT", "B_DIRECT_CHECKED", "C_SYSTEM", "D_INVERTED", "E_RANDOM_AUDITOR", "F_ORACLE_AUDITOR"),
    )
    plan = build_trial_plan(cfg, models)
    model_dependent = [p for p in plan if p.arm in {"A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED"}]
    observed = [p.model_index for p in model_dependent]
    transitions = sum(a != b for a, b in zip(observed, observed[1:]))
    assert transitions <= len(models) - 1


def test_decisive_config_uses_010_hardened_ollama_settings():
    import yaml
    from pathlib import Path

    raw = yaml.safe_load(Path("configs/decisive.yaml").read_text(encoding="utf-8"))
    for spec in raw["models"]:
        assert spec["timeout_s"] >= 600
        assert spec["max_retries"] == 2
        assert spec["think"] is False
        assert spec["format_json"] is True
        assert spec["context_limit"] == 8192
