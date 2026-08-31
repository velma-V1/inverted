from __future__ import annotations

import httpx
import pytest

import inverted.cli as cli
from inverted.arms import Arm
from inverted.models import CompletionResult, MockModelAdapter, ModelCallError, OllamaAdapter
from inverted.runner import ExperimentConfig, run_experiment
from inverted.telemetry import ModelCallRecord


def _record(model: str, role: str, response: str) -> ModelCallRecord:
    return ModelCallRecord(
        call_id=f"{model}-{role}", run_id="preflight", trial_id=f"{model}-{role}", candidate_id=None,
        role=role, model=model, provider="ollama", start_ts="2026-08-31T00:00:00+00:00",
        end_ts="2026-08-31T00:00:01+00:00", latency_s=1.0, status_code=200,
        raw_provider_telemetry={
            "attempts": [{
                "attempt": 0, "status_code": 200, "content": response, "thinking": None,
                "prompt_eval_count": 10, "eval_count": 5, "done_reason": "stop",
            }],
            "content": response, "thinking": None, "prompt_eval_count": 10,
            "eval_count": 5, "done_reason": "stop",
        },
        raw_usage={"prompt_eval_count": 10, "eval_count": 5}, response=response,
    )


class PreflightOllama:
    provider = "ollama"

    def __init__(self, model: str):
        self.model = model
        self.context_limit = 8192
        self.think = False
        self.format_json = True
        self.unload_calls = 0

    def complete(self, messages, *, role, context):
        text = '{"accept": true}' if role == "preflight_auditor" else '{"actions": []}'
        return CompletionResult(text=text, record=_record(self.model, role, text), raw={})

    def unload(self):
        self.unload_calls += 1


def test_preflight_unloads_each_ollama_model_after_its_probe_block():
    models = [PreflightOllama("m1"), PreflightOllama("m2"), PreflightOllama("m3")]
    cli._preflight_models(models, cells_per_model=12, max_generation_censored=0)
    assert [model.unload_calls for model in models] == [1, 1, 1]


def test_runner_unloads_model_before_switching_and_after_final_block():
    class TrackedMock(MockModelAdapter):
        def __init__(self, model: str, seed: int):
            super().__init__(model=model, seed=seed)
            self.unload_calls = 0

        def unload(self):
            self.unload_calls += 1

    models = [TrackedMock("m1", 1), TrackedMock("m2", 2)]
    config = ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.8,), seeds=(1,), epochs=1,
        arms=(Arm.A_DIRECT.value,),
    )
    run_experiment(config, models, run_id="model-switch-unload")
    assert [model.unload_calls for model in models] == [1, 1]


def test_hard_ollama_500_is_not_retried_and_preserves_server_error(monkeypatch):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
        return httpx.Response(
            500,
            request=request,
            json={"error": "model requires more system memory (19.0 GiB) than is available (12.0 GiB)"},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="too-big", max_retries=2, retry_backoff_s=0)
    with pytest.raises(ModelCallError) as exc_info:
        model.complete([{"role": "user", "content": "x"}], role="executor", context={})

    assert calls == 1
    message = exc_info.value.record.error_message or ""
    assert "model requires more system memory" in message
    attempts = exc_info.value.record.raw_provider_telemetry["attempts"]
    assert len(attempts) == 1
    assert "model requires more system memory" in attempts[0]["error_message"]


def test_transient_500_still_retries(monkeypatch):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
        if calls == 1:
            return httpx.Response(500, request=request, json={"error": "temporary runner unavailable"})
        return httpx.Response(
            200,
            request=request,
            json={
                "message": {"content": "{}"}, "done_reason": "stop",
                "prompt_eval_count": 1, "eval_count": 1,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="m", max_retries=2, retry_backoff_s=0)
    result = model.complete([{"role": "user", "content": "x"}], role="executor", context={})
    assert result.text == "{}"
    assert calls == 2
