import json
from pathlib import Path

import pytest
import yaml

from inverted.cli import _preflight_models
from inverted.models import CompletionResult, GenerationCensored
from inverted.telemetry import ModelCallRecord


def _record(*, role: str, model: str, content: str, thinking: str, prompt_tokens: int, output_tokens: int, done_reason: str, error_class: str | None = None) -> ModelCallRecord:
    return ModelCallRecord(
        call_id="c",
        run_id="preflight",
        trial_id="t",
        candidate_id=None,
        role=role,
        model=model,
        provider="ollama",
        start_ts="2026-08-31T00:00:00+00:00",
        end_ts="2026-08-31T00:00:01+00:00",
        latency_s=1.0,
        input_tokens=prompt_tokens,
        output_tokens=output_tokens,
        total_tokens=prompt_tokens + output_tokens,
        finish_reason=done_reason,
        error_class=error_class,
        raw_provider_telemetry={
            "attempts": [{
                "attempt": 0,
                "status_code": 200,
                "thinking": thinking,
                "content": content,
                "prompt_eval_count": prompt_tokens,
                "eval_count": output_tokens,
                "done_reason": done_reason,
            }],
            "thinking": thinking,
            "content": content,
            "prompt_eval_count": prompt_tokens,
            "eval_count": output_tokens,
            "done_reason": done_reason,
        },
    )


class _AlwaysGood:
    provider = "ollama"
    model = "good"

    def complete(self, messages, *, role, context):
        text = '{"actions":[]}' if role == "preflight_executor" else '{"accept":true,"failed_requirements":[],"reason":"ok"}'
        return CompletionResult(
            text,
            _record(role=role, model=self.model, content=text, thinking="", prompt_tokens=17, output_tokens=9, done_reason="stop"),
            {},
        )


class _CensorOnce(_AlwaysGood):
    model = "censor-once"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, *, role, context):
        self.calls += 1
        if self.calls == 1:
            rec = _record(
                role=role,
                model=self.model,
                content="",
                thinking="budget used",
                prompt_tokens=111,
                output_tokens=1024,
                done_reason="length",
                error_class="GENERATION_CENSORED",
            )
            raise GenerationCensored("budget exhausted", rec)
        return super().complete(messages, role=role, context=context)


def test_decisive_config_encodes_zero_censorship_not_percentage_threshold():
    raw = yaml.safe_load(Path("configs/decisive.yaml").read_text(encoding="utf-8"))
    preflight = raw["preflight"]
    assert preflight["cells_per_model"] == 12
    assert preflight["max_generation_censored"] == 0
    assert "censorship_threshold" not in preflight


def test_preflight_reports_zero_censorship_policy_and_passes_zero_of_twelve():
    captured = []
    evidence = _preflight_models(
        [_AlwaysGood()],
        cells_per_model=12,
        max_generation_censored=0,
        telemetry_callback=captured.append,
    )
    assert len(captured) == 12
    assert evidence[0]["generation_censored"] == 0
    assert evidence[0]["cells_attempted"] == 12
    assert evidence[0]["censorship_policy"] == "ZERO_CENSORSHIP"
    assert evidence[0]["max_generation_censored"] == 0


def test_preflight_aborts_on_one_of_twelve_censored_without_percentage_language():
    captured = []
    with pytest.raises(RuntimeError, match=r"zero-censorship preflight failed.*1/12"):
        _preflight_models(
            [_CensorOnce()],
            cells_per_model=12,
            max_generation_censored=0,
            telemetry_callback=captured.append,
        )
    assert len(captured) == 12
    assert sum(r.error_class == "GENERATION_CENSORED" for r in captured) == 1


def test_preflight_success_and_censored_records_persist_required_ollama_telemetry_fields(tmp_path):
    records = []
    with pytest.raises(RuntimeError):
        _preflight_models(
            [_CensorOnce()],
            cells_per_model=12,
            max_generation_censored=0,
            telemetry_callback=records.append,
        )

    assert any(r.error_class == "GENERATION_CENSORED" for r in records)
    assert any(r.error_class is None for r in records)
    for record in records:
        telemetry = record.raw_provider_telemetry
        assert telemetry is not None
        for key in ("thinking", "content", "prompt_eval_count", "eval_count", "done_reason"):
            assert key in telemetry
        assert telemetry["attempts"]
        for attempt in telemetry["attempts"]:
            for key in ("thinking", "content", "prompt_eval_count", "eval_count", "done_reason"):
                assert key in attempt
