from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
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


class GenerationCensored(ModelCallError):
    """Generation consumed its output budget without producing final content."""


class EmptyModelResponse(RuntimeError):
    pass


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
            call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
            role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency,
            input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens,
            eval_duration_s=latency, status_code=200, finish_reason="stop", params={"seed": self.seed},
            raw_usage={"prompt_tokens": input_tokens, "completion_tokens": output_tokens, "total_tokens": input_tokens + output_tokens},
            prompt=messages if self.capture_content else None, response=text if self.capture_content else None,
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
            record = ModelCallRecord(
                call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
                role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency, status_code=status,
                error_class=type(exc).__name__, error_message=str(exc), timeout=isinstance(exc, httpx.TimeoutException), params={"temperature": self.temperature, "max_tokens": self.max_tokens}, prompt=messages if self.capture_content else None,
            )
            raise ModelCallError(str(exc), record) from exc


class OllamaAdapter:
    provider = "ollama"
    _RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
    _CENSORED_REASONS = {"length", "max_tokens", "max_token", "token_limit", "token-limit"}
    _HARD_500_MARKERS = (
        "requires more system memory",
        "out of memory",
        "memory layout cannot be allocated",
        "model failed to load",
        "failed to load model",
        "resource limitations",
        "runner process has terminated",
        "cuda error",
        "rocm error",
    )
    _EXECUTOR_SCHEMA = {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["set", "resolve", "delete"]},
                        "path": {"type": "string"},
                        "value": {"type": ["string", "number", "boolean", "object", "array", "null"]},
                    },
                    "required": ["op", "path"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["actions"],
        "additionalProperties": False,
    }
    _AUDITOR_SCHEMA = {
        "type": "object",
        "properties": {
            "accept": {"type": "boolean"},
            "failed_requirements": {"type": "array", "items": {"type": "string"}, "maxItems": 64},
            "reason": {"type": "string", "maxLength": 1024},
        },
        "required": ["accept", "failed_requirements", "reason"],
        "additionalProperties": False,
    }
    _PREFLIGHT_SCHEMA = {
        "type": "object",
        "properties": {"ok": {"const": True}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434", timeout_s: float = 120.0, capture_content: bool = True, temperature: float = 0.0, max_tokens: int = 1024, max_retries: int = 0, retry_backoff_s: float = 1.0, think: bool | str | None = None, format_json: bool = False, context_limit: int | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.capture_content = capture_content
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_s = max(0.0, float(retry_backoff_s))
        self.think = think
        self.format_json = bool(format_json)
        self.context_limit = int(context_limit) if context_limit is not None else None

    @staticmethod
    def _status(exc: Exception) -> int | None:
        return exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None

    @staticmethod
    def _server_body(exc: Exception) -> str:
        if not isinstance(exc, httpx.HTTPStatusError):
            return ""
        try:
            return exc.response.text.strip()
        except Exception:
            return ""

    def _error_message(self, exc: Exception) -> str:
        body = self._server_body(exc)
        if body:
            return f"{exc} | Ollama response: {body}"
        return str(exc)

    def _hard_server_error(self, exc: Exception) -> bool:
        if self._status(exc) != 500:
            return False
        body = self._server_body(exc).lower()
        return any(marker in body for marker in self._HARD_500_MARKERS)

    def _retryable(self, exc: Exception) -> bool:
        if isinstance(exc, GenerationCensored):
            return False
        if self._hard_server_error(exc):
            return False
        if isinstance(exc, (httpx.TransportError, json.JSONDecodeError, EmptyModelResponse)):
            return True
        return self._status(exc) in self._RETRYABLE_STATUS

    def unload(self) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": [], "stream": False, "keep_alive": 0},
            timeout=min(self.timeout_s, 30.0),
        )
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"status_code": response.status_code, "text": response.text}

    def _format_for_role(self, role: str) -> str | dict[str, Any] | None:
        if not self.format_json:
            return None
        normalized = role.removeprefix("preflight_")
        if normalized == "executor":
            return self._EXECUTOR_SCHEMA
        if normalized == "auditor":
            return self._AUDITOR_SCHEMA
        if role == "preflight":
            return self._PREFLIGHT_SCHEMA
        return "json"

    def _payload(self, messages: list[dict[str, str]], role: str) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": self.temperature, "num_predict": self.max_tokens}
        if self.context_limit is not None:
            options["num_ctx"] = self.context_limit
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False, "options": options}
        if self.think is not None:
            payload["think"] = self.think
        response_format = self._format_for_role(role)
        if response_format is not None:
            payload["format"] = response_format
        return payload

    def _attempt_from_raw(self, raw: dict[str, Any], attempt: int, status_code: int | None = 200) -> dict[str, Any]:
        message = raw.get("message") or {}
        return {
            "attempt": attempt,
            "status_code": status_code,
            "content": str(message.get("content") or ""),
            "thinking": message.get("thinking"),
            "prompt_eval_count": raw.get("prompt_eval_count"),
            "eval_count": raw.get("eval_count"),
            "done_reason": raw.get("done_reason"),
        }

    def _is_generation_censored(self, raw: dict[str, Any], text: str) -> bool:
        if text.strip():
            return False
        eval_count = raw.get("eval_count")
        done_reason = str(raw.get("done_reason") or "").lower()
        exhausted = isinstance(eval_count, int) and eval_count >= self.max_tokens
        return exhausted or done_reason in self._CENSORED_REASONS

    def _record(self, *, context: dict[str, Any], role: str, start_ts: str, latency: float, attempts: list[dict[str, Any]], raw: dict[str, Any] | None = None, response_text: str | None = None, error_class: str | None = None, error_message: str | None = None, timeout: bool = False, status_code: int | None = None) -> ModelCallRecord:
        raw = raw or {}
        input_tokens = raw.get("prompt_eval_count")
        output_tokens = raw.get("eval_count")
        total_tokens = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
        ns = 1_000_000_000
        return ModelCallRecord(
            call_id=_id(context, "call_id", "call"), run_id=_id(context, "run_id", "run"), trial_id=_id(context, "trial_id", "trial"), candidate_id=context.get("candidate_id"),
            role=role, model=self.model, provider=self.provider, start_ts=start_ts, end_ts=_now(), latency_s=latency,
            input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens,
            prompt_eval_duration_s=(raw.get("prompt_eval_duration") / ns) if raw.get("prompt_eval_duration") is not None else None,
            eval_duration_s=(raw.get("eval_duration") / ns) if raw.get("eval_duration") is not None else None,
            load_duration_s=(raw.get("load_duration") / ns) if raw.get("load_duration") is not None else None,
            status_code=status_code, error_class=error_class, error_message=error_message, timeout=timeout,
            retry_number=max(0, len(attempts) - 1), retry_reason=(attempts[-2].get("error_class") + ": " + attempts[-2].get("error_message", "")) if len(attempts) > 1 and attempts[-2].get("error_class") else None,
            finish_reason=raw.get("done_reason"),
            params={"temperature": self.temperature, "max_tokens": self.max_tokens, "think": self.think, "format_json": self.format_json, "context_limit": self.context_limit},
            raw_usage={"prompt_eval_count": input_tokens, "eval_count": output_tokens},
            raw_provider_telemetry={"attempts": attempts, "thinking": (raw.get("message") or {}).get("thinking"), "content": (raw.get("message") or {}).get("content"), "done_reason": raw.get("done_reason"), "eval_count": output_tokens, "prompt_eval_count": input_tokens},
            prompt=context.get("_prompt") if self.capture_content else None,
            response=response_text if self.capture_content else None,
        )

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]) -> CompletionResult:
        start_ts, overall_start = _now(), time.perf_counter()
        payload = self._payload(messages, role)
        attempts: list[dict[str, Any]] = []
        context = dict(context)
        context["_prompt"] = messages
        last_exc: Exception | None = None
        last_error_message: str | None = None

        for attempt in range(self.max_retries + 1):
            raw: dict[str, Any] | None = None
            try:
                response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s)
                response.raise_for_status()
                raw = response.json()
                text = str((raw.get("message") or {}).get("content") or "")
                event = self._attempt_from_raw(raw, attempt, response.status_code)
                if self._is_generation_censored(raw, text):
                    event["error_class"] = "GENERATION_CENSORED"
                    event["error_message"] = "empty content after generation budget exhaustion"
                    attempts.append(event)
                    record = self._record(context=context, role=role, start_ts=start_ts, latency=time.perf_counter() - overall_start, attempts=attempts, raw=raw, response_text=text, error_class="GENERATION_CENSORED", error_message=event["error_message"], status_code=response.status_code)
                    raise GenerationCensored(event["error_message"], record)
                if not text.strip():
                    event["error_class"] = "EmptyModelResponse"
                    event["error_message"] = "empty Ollama content without generation-budget exhaustion"
                    attempts.append(event)
                    raise EmptyModelResponse(event["error_message"])
                attempts.append(event)
                record = self._record(context=context, role=role, start_ts=start_ts, latency=time.perf_counter() - overall_start, attempts=attempts, raw=raw, response_text=text, status_code=response.status_code)
                return CompletionResult(text, record, raw)
            except GenerationCensored:
                raise
            except Exception as exc:
                last_exc = exc
                last_error_message = self._error_message(exc)
                if raw is None:
                    attempts.append({"attempt": attempt, "status_code": self._status(exc), "content": None, "thinking": None, "prompt_eval_count": None, "eval_count": None, "done_reason": None, "error_class": type(exc).__name__, "error_message": last_error_message, "timeout": isinstance(exc, httpx.TimeoutException)})
                if attempt >= self.max_retries or not self._retryable(exc):
                    break
                if self.retry_backoff_s:
                    time.sleep(self.retry_backoff_s * (2 ** attempt))

        assert last_exc is not None
        final_message = last_error_message or str(last_exc)
        record = self._record(context=context, role=role, start_ts=start_ts, latency=time.perf_counter() - overall_start, attempts=attempts, error_class=type(last_exc).__name__, error_message=final_message, timeout=isinstance(last_exc, httpx.TimeoutException), status_code=self._status(last_exc))
        raise ModelCallError(final_message, record) from last_exc

    def preflight(self) -> dict[str, Any]:
        messages = [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": 'Return exactly {"ok":true}.'}]
        result = self.complete(messages, role="preflight", context={"run_id": "preflight", "trial_id": f"preflight-{self.model}", "call_id": f"preflight-{self.model}"})
        try:
            parsed = json.loads(result.text)
        except json.JSONDecodeError as exc:
            result.record.error_class = "PreflightInvalidJSON"
            result.record.error_message = str(exc)
            raise ModelCallError(f"preflight invalid JSON for {self.model}: {exc}", result.record) from exc
        if not isinstance(parsed, dict) or parsed.get("ok") is not True:
            result.record.error_class = "PreflightUnexpectedResponse"
            result.record.error_message = result.text
            raise ModelCallError(f"preflight unexpected response for {self.model}: {result.text}", result.record)
        return {"model": self.model, "provider": self.provider, "response": parsed, "latency_s": result.record.latency_s, "retry_number": result.record.retry_number}
