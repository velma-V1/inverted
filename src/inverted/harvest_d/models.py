from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Protocol
from urllib.request import Request, urlopen


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json(value):
    raise ValueError(f"non-finite JSON constant: {value}")


class ModelAdapter(Protocol):
    model_id: str

    def complete(self, prompt: str, system: str | None = None) -> "ModelResponse": ...


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    raw: dict[str, Any]


class OllamaChatAdapter:
    DEFAULT_GENERATION_OPTIONS = {
        "temperature": 0.0,
        "seed": 20260902,
        "num_ctx": 4096,
    }

    def __init__(
        self,
        model_id: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 300.0,
        opener: Callable[..., Any] = urlopen,
        generation_options: dict[str, Any] | None = None,
        think: bool | str | None = None,
    ) -> None:
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener
        self.generation_options = dict(generation_options or self.DEFAULT_GENERATION_OPTIONS)
        self.think = think

    def request_bytes(self, prompt: str, system: str | None = None) -> bytes:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
            "options": self.generation_options,
        }
        if self.think is not None:
            payload["think"] = self.think
        return json.dumps(payload).encode("utf-8")

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        return self.complete_request_bytes(self.request_bytes(prompt, system))

    def complete_request_bytes(self, body: bytes) -> ModelResponse:
        if not isinstance(body, bytes):
            raise TypeError("body must be exact bytes")
        req = Request(
            self.base_url + "/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        with self._opener(req, timeout=self.timeout) as response:
            payload = json.loads(
                response.read().decode("utf-8"),
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_reject_nonfinite_json,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if not isinstance(payload, dict):
            raise ValueError("Ollama response payload must be a dict")
        response_model = payload.get("model")
        if not isinstance(response_model, str) or not response_model.strip():
            raise ValueError("Ollama response model must be a nonempty string")
        total_duration = payload.get("total_duration")
        latency_ms = float(total_duration) / 1_000_000.0 if total_duration is not None else elapsed_ms
        return ModelResponse(
            str(payload.get("message", {}).get("content", "")),
            response_model,
            int(payload.get("prompt_eval_count", 0) or 0),
            int(payload.get("eval_count", 0) or 0),
            latency_ms,
            payload,
        )
