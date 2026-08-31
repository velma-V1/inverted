import httpx
import pytest

from inverted.arms import Arm, Budget, run_arm
from inverted.cli import _build_models, _preflight_models
from inverted.models import CompletionResult, GenerationCensored, ModelCallError, OllamaAdapter
from inverted.runner import ExperimentConfig, build_trial_plan
from inverted.tasks import generate_task
from inverted.telemetry import ModelCallRecord


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


def _record(role="executor", model="broken", *, error_class=None, error_message=None, timeout=False):
    return ModelCallRecord(
        call_id="c", run_id="r", trial_id="t", candidate_id=None,
        role=role, model=model, provider="ollama",
        start_ts="2026-08-31T00:00:00+00:00", end_ts="2026-08-31T00:00:01+00:00",
        latency_s=1.0, error_class=error_class, error_message=error_message, timeout=timeout,
        retry_number=2 if error_class else 0, retry_reason=(f"{error_class}: {error_message}" if error_class else None),
    )


def _error_record():
    return _record(error_class="ReadTimeout", error_message="stalled", timeout=True)


def test_ollama_retries_transient_no_response_and_records_every_attempt(monkeypatch):
    attempts = []

    def fake_post(url, *, json, timeout):
        attempts.append((url, json, timeout))
        if len(attempts) < 3:
            raise httpx.ReadTimeout("no model response", request=httpx.Request("POST", url))
        return _Response(payload={
            "message": {"content": '{"accept":true}', "thinking": ""},
            "done_reason": "stop",
            "prompt_eval_count": 12,
            "eval_count": 4,
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="qwen", timeout_s=600, max_retries=2, retry_backoff_s=0, think=False, format_json=True, context_limit=8192)
    result = model.complete([{"role": "user", "content": "x"}], role="auditor", context=_ctx())

    assert len(attempts) == 3
    assert result.record.retry_number == 2
    telemetry = result.record.raw_provider_telemetry
    assert len(telemetry["attempts"]) == 3
    assert telemetry["attempts"][-1]["content"] == '{"accept":true}'
    assert telemetry["attempts"][-1]["thinking"] == ""
    assert telemetry["attempts"][-1]["eval_count"] == 4
    assert telemetry["attempts"][-1]["prompt_eval_count"] == 12
    assert telemetry["attempts"][-1]["done_reason"] == "stop"
    payload = attempts[-1][1]
    assert payload["think"] is False
    assert payload["format"] == "json"
    assert payload["options"]["num_ctx"] == 8192


def test_empty_content_at_generation_budget_is_generation_censored(monkeypatch):
    def fake_post(url, *, json, timeout):
        return _Response(payload={
            "message": {"content": "", "thinking": "used the whole budget"},
            "done_reason": "length",
            "prompt_eval_count": 111,
            "eval_count": 1024,
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="qwen", max_tokens=1024, max_retries=2, retry_backoff_s=0, think=False, format_json=True)
    with pytest.raises(GenerationCensored) as excinfo:
        model.complete([{"role": "user", "content": "x"}], role="executor", context=_ctx())
    record = excinfo.value.record
    assert record.error_class == "GENERATION_CENSORED"
    assert record.input_tokens == 111
    assert record.output_tokens == 1024
    assert record.finish_reason == "length"
    attempt = record.raw_provider_telemetry["attempts"][-1]
    assert attempt["thinking"] == "used the whole budget"
    assert attempt["content"] == ""
    assert attempt["eval_count"] == 1024
    assert attempt["done_reason"] == "length"


def test_empty_content_without_exhaustion_is_retried_as_transport_like_failure(monkeypatch):
    calls = 0

    def fake_post(url, *, json, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _Response(payload={"message": {"content": "", "thinking": ""}, "done_reason": "stop", "eval_count": 2})
        return _Response(payload={"message": {"content": '{"actions":[]}', "thinking": ""}, "done_reason": "stop", "eval_count": 5})

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="qwen", max_retries=2, retry_backoff_s=0, think=False, format_json=True)
    result = model.complete([{"role": "user", "content": "x"}], role="executor", context=_ctx())
    assert calls == 2
    assert result.record.retry_number == 1
    assert result.record.raw_provider_telemetry["attempts"][0]["error_class"] == "EmptyModelResponse"


def test_ollama_exhausted_transport_failure_aborts_instead_of_returning_scored_failure(monkeypatch):
    def fake_post(url, *, json, timeout):
        raise httpx.ReadTimeout("stalled", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="qwen", max_retries=2, retry_backoff_s=0)
    with pytest.raises(ModelCallError) as excinfo:
        model.complete([{"role": "user", "content": "x"}], role="executor", context=_ctx())
    assert excinfo.value.record.retry_number == 2
    assert excinfo.value.record.timeout is True
    assert len(excinfo.value.record.raw_provider_telemetry["attempts"]) == 3


def test_exhausted_model_call_error_aborts_trial_instead_of_becoming_scientific_failure():
    class BrokenModel:
        provider = "ollama"
        model = "broken"

        def complete(self, messages, *, role, context):
            raise ModelCallError("stalled", _error_record())

    task = generate_task("state", 1, 123)
    with pytest.raises(ModelCallError):
        run_arm(Arm.A_DIRECT, task, BrokenModel(), 0.2, 1, "r", Budget(), epoch=0)


def test_preflight_runs_12_representative_cells_per_model():
    class ContractModel:
        provider = "ollama"
        model = "contract"

        def __init__(self):
            self.roles = []

        def complete(self, messages, *, role, context):
            self.roles.append(role)
            text = '{"actions":[]}' if role == "preflight_executor" else '{"accept":false,"failed_requirements":["probe"],"reason":"probe"}'
            return CompletionResult(text, _record(role=role, model=self.model), {})

    model = ContractModel()
    evidence = _preflight_models([model], cells_per_model=12, censorship_threshold=0.05)
    assert len(model.roles) == 12
    assert model.roles.count("preflight_executor") == 6
    assert model.roles.count("preflight_auditor") == 6
    assert evidence[0]["cells_attempted"] == 12
    assert evidence[0]["generation_censored"] == 0
    assert evidence[0]["censorship_rate"] == 0.0


def test_preflight_aborts_if_censorship_rate_exceeds_threshold():
    class CensorOnce:
        provider = "ollama"
        model = "censor-once"

        def __init__(self):
            self.calls = 0

        def complete(self, messages, *, role, context):
            self.calls += 1
            if self.calls == 1:
                rec = _record(role=role, model=self.model, error_class="GENERATION_CENSORED", error_message="budget exhausted")
                rec.output_tokens = 1024
                rec.finish_reason = "length"
                raise GenerationCensored("budget exhausted", rec)
            text = '{"actions":[]}' if role == "preflight_executor" else '{"accept":true,"failed_requirements":[],"reason":"ok"}'
            return CompletionResult(text, _record(role=role, model=self.model), {})

    with pytest.raises(RuntimeError, match="censorship.*threshold"):
        _preflight_models([CensorOnce()], cells_per_model=12, censorship_threshold=0.05)


def test_preflight_rejects_malformed_auditor_contract_before_campaign():
    class Malformed:
        provider = "ollama"
        model = "malformed"

        def complete(self, messages, *, role, context):
            text = '{"actions":[]}' if role == "preflight_executor" else "NOT JSON"
            return CompletionResult(text, _record(role=role, model=self.model), {})

    with pytest.raises(ValueError, match="preflight.*auditor"):
        _preflight_models([Malformed()], cells_per_model=12, censorship_threshold=0.05)


def test_decisive_ollama_models_have_frozen_reliability_contract():
    raw = {"models": [{"provider": "ollama", "model": "m", "timeout_s": 600, "max_retries": 2, "retry_backoff_s": 5, "think": False, "format_json": True, "context_limit": 8192}]}
    model = _build_models(raw, capture_content=True)[0]
    assert model.timeout_s == 600
    assert model.max_retries == 2
    assert model.think is False
    assert model.format_json is True
    assert model.context_limit == 8192


def test_model_dependent_plan_is_grouped_by_model_to_avoid_ollama_swap_thrash():
    models = [type("M", (), {"provider": "ollama", "model": name})() for name in ("q", "g", "d")]
    cfg = ExperimentConfig(families=("state",), complexities=(1,), qualities=(0.2, 0.8), seeds=(1, 2), epochs=1, arms=("A_DIRECT", "B_DIRECT_CHECKED", "C_SYSTEM", "D_INVERTED", "E_RANDOM_AUDITOR", "F_ORACLE_AUDITOR"))
    plan = build_trial_plan(cfg, models)
    model_dependent = [p for p in plan if p.arm in {"A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED"}]
    observed = [p.model_index for p in model_dependent]
    transitions = sum(a != b for a, b in zip(observed, observed[1:]))
    assert transitions <= len(models) - 1


def test_decisive_config_uses_010_hardened_ollama_and_preflight_settings():
    import yaml
    from pathlib import Path

    raw = yaml.safe_load(Path("configs/decisive.yaml").read_text(encoding="utf-8"))
    for spec in raw["models"]:
        assert spec["timeout_s"] >= 600
        assert spec["max_retries"] == 2
        assert spec["think"] is False
        assert spec["format_json"] is True
        assert spec["context_limit"] == 8192
    assert raw["preflight"]["cells_per_model"] == 12
    assert raw["preflight"]["censorship_threshold"] == 0.05
