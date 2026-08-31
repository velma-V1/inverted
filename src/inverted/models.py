from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import random
import time
import uuid
from typing import Any

import httpx

from .telemetry import ModelCallRecord


@dataclass
class CompletionResult:
    text: str
    record: ModelCallRecord
    raw: dict[str, Any]


class ModelCallError(RuntimeError):
    def __init__(self, message: str, record: ModelCallRecord):
        super().__init__(message)
        self.record = record


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(context: dict[str, Any], key: str, prefix: str) -> str:
    return str(context.get(key) or f"{prefix}-{uuid.uuid4().hex[:16]}")


def _rough_mock_tokens(value: Any) -> int:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    return max(1, len(text.split()))


class MockModelAdapter:
    provider = "mock"

    def __init__(self, model: str = "mock", seed: int = 0, executor_accuracy: float = 1.0, auditor_accuracy: float = 1.0, capture_content: bool = True):
        self.model = model
        self.seed = seed
        self.executor_accuracy = executor_accuracy
        self.auditor_accuracy = auditor_accuracy
        self.capture_content = capture_content
        self.malformed_roles: set[str] = set()

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]) -> CompletionResult:
        start_ts = _now()
        start = time.perf_counter()
        text = str(context.get("mock_text", "{}"))
        latency = max(time.perf_counter() - start, 1e-9)
        input_tokens = _rough_mock_tokens(messages)
        output_tokens = _rough_mock_tokens(text)
        record = ModelCallRecord(
            call_id=_id(context, "call_id", "call"),
            run_id=_id(context, "run_id", "run"),
            trial_id=_id(context, "trial_id", "trial"),
            candidate_id=context.get("candidate_id"),
            role=role,
            model=self.model,
            provider=self.provider,
            start_ts=start_ts,
            end_ts=_now(),
            latency_s=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            eval_duration_s=latency,
            status_code=200,
            finish_reason="stop",
            params={"seed": self.seed},
            raw_usage={"prompt_tokens": input_tokens, "completion_tokens": output_tokens, "total_tokens": input_tokens + output_tokens},
            prompt=messages if self.capture_content else None,
            response=text if self.capture_content else None,
        )
        return CompletionResult(text, record, {"mock": True})


class OpenAICompatibleAdapter:
    provider = "openai-compatible"

    def __init__(self, model: str, base_url: str, api_key: str | None, timeout_s: float = 120.0, capture_content: bool = True, temperature: float = 0.0, max_tokens: int = 1024, price_per_m_input: float | None = None, price_per_m_output: float | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.capture_content = capture_content
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.price_per_m_input = price_per_m_input
        self.price_per_m_output = price_per_m_output

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]) -> CompletionResult:
        start_ts, start = _now(), time.perf_counter()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature, "max_tokens": self.max_tokens}
        try:
            response = httpx.post(f"{self.base_url}/v1/chat/completions", headers=headers, json=payload, timeout=self.timeout_s)
            response.raise_for_status()
            raw = response.json()
            latency = time.perf_counter() - start
            usage = raw.get("usage") or {}
            prompt_details = usage.get("prompt_tokens_details") or {}
            completion_details = usage.get("completion_tokens_details") or {}
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            reasoning_tokens = completion_details.get("reasoning_tokens")
            cached_tokens = prompt_details.get("cached_tokens")
            cost = None
            if input_tokens is not None and output_tokens is not None and self.price_per_m_input is not None and self.price_per_m_output is not None:
                cost = (input_tokens / 1_000_000) * self.price_per_m_input + (output_tokens / 1_000_000) * self.price_per_m_output
            choice = (raw.get("choices") or [{}])[0]
            text = str((choice.get("message") or {}).get("content") or "")
            record = ModelCallRecord(
                call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
                role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency,
                input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, reasoning_tokens=reasoning_tokens, cached_tokens=cached_tokens,
                status_code=response.status_code, finish_reason=choice.get("finish_reason"), params={"temperature": self.temperature, "max_tokens": self.max_tokens}, cost_usd=cost,
                raw_usage=usage, raw_provider_telemetry={k: v for k, v in raw.items() if k not in {"choices", "usage"}}, prompt=messages if self.capture_content else None, response=text if self.capture_content else None,
            )
            return CompletionResult(text, record, raw)
        except Exception as exc:
            latency = time.perf_counter() - start
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            timeout = isinstance(exc, httpx.TimeoutException)
            record = ModelCallRecord(
                call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
                role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency, status_code=status,
                error_class=type(exc).__name__, error_message=str(exc), timeout=timeout, params={"temperature": self.temperature, "max_tokens": self.max_tokens},
                prompt=messages if self.capture_content else None,
            )
            raise ModelCallError(str(exc), record) from exc


class OllamaAdapter:
    provider = "ollama"

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434", timeout_s: float = 120.0, capture_content: bool = True, temperature: float = 0.0, max_tokens: int = 1024):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.capture_content = capture_content
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]) -> CompletionResult:
        start_ts, start = _now(), time.perf_counter()
        payload = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": self.temperature, "num_predict": self.max_tokens}}
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s)
            response.raise_for_status()
            raw = response.json()
            latency = time.perf_counter() - start
            text = str((raw.get("message") or {}).get("content") or "")
            input_tokens, output_tokens = raw.get("prompt_eval_count"), raw.get("eval_count")
            total_tokens = input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
            ns = 1_000_000_000
            record = ModelCallRecord(
                call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
                role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency,
                input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens,
                prompt_eval_duration_s=(raw.get("prompt_eval_duration") / ns) if raw.get("prompt_eval_duration") is not None else None,
                eval_duration_s=(raw.get("eval_duration") / ns) if raw.get("eval_duration") is not None else None,
                load_duration_s=(raw.get("load_duration") / ns) if raw.get("load_duration") is not None else None,
                status_code=response.status_code, finish_reason=raw.get("done_reason"), params={"temperature": self.temperature, "max_tokens": self.max_tokens},
                raw_usage={"prompt_eval_count": input_tokens, "eval_count": output_tokens},
                raw_provider_telemetry={k: v for k, v in raw.items() if k not in {"message"}}, prompt=messages if self.capture_content else None, response=text if self.capture_content else None,
            )
            return CompletionResult(text, record, raw)
        except Exception as exc:
            latency = time.perf_counter() - start
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            record = ModelCallRecord(
                call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
                role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency, status_code=status,
                error_class=type(exc).__name__, error_message=str(exc), timeout=isinstance(exc, httpx.TimeoutException), params={"temperature": self.temperature, "max_tokens": self.max_tokens}, prompt=messages if self.capture_content else None,
            )
            raise ModelCallError(str(exc), record) from exc
