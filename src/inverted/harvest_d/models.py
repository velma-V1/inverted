from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Protocol
from urllib.request import Request, urlopen

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
    def __init__(self, model_id: str, *, base_url: str = "http://127.0.0.1:11434", timeout: float = 300.0,
                 opener: Callable[..., Any] = urlopen) -> None:
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({"model": self.model_id, "messages": messages, "stream": False}).encode("utf-8")
        req = Request(self.base_url + "/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST")
        start = time.perf_counter()
        with self._opener(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        total_duration = payload.get("total_duration")
        latency_ms = float(total_duration) / 1_000_000.0 if total_duration is not None else elapsed_ms
        return ModelResponse(str(payload.get("message", {}).get("content", "")), str(payload.get("model", self.model_id)),
                             int(payload.get("prompt_eval_count", 0) or 0), int(payload.get("eval_count", 0) or 0), latency_ms, payload)
