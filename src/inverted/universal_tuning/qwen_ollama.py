from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.request import Request, urlopen

from .core import AtomicTask, Profile
from .runner import AdapterCompletion
from .scheduler import ModelMetadata

MODEL_ID = "qwen3.5:9b-q8_0"
NUM_CTX = 8192
FINAL_MAX_TOKENS = 768


class QwenOllamaAdapter:
    def __init__(
        self, model_id: str = MODEL_ID, base_url: str = "http://127.0.0.1:11434",
        timeout: float = 300.0, opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener
        self.metadata = ModelMetadata()

    def runtime_provenance(self) -> dict[str, str]:
        payloads: dict[str, Any] = {}
        for endpoint in ("version", "tags"):
            request = Request(self.base_url + f"/api/{endpoint}", method="GET")
            with self._opener(request, timeout=min(self.timeout, 30.0)) as response:
                payloads[endpoint] = json.loads(response.read().decode("utf-8"))
        version = payloads["version"].get("version") if isinstance(payloads["version"], dict) else None
        models = payloads["tags"].get("models") if isinstance(payloads["tags"], dict) else None
        if not isinstance(version, str) or not version.strip() or not isinstance(models, list):
            raise ValueError("Ollama provenance is malformed")
        matches = [item for item in models if isinstance(item, dict) and item.get("name") == self.model_id]
        if len(matches) != 1 or not isinstance(matches[0].get("digest"), str):
            raise ValueError("Ollama provenance requires exactly one matching model digest")
        return {
            "provider": "ollama", "base_url": self.base_url,
            "ollama_version": version.strip(), "model": self.model_id,
            "model_digest": matches[0]["digest"].strip(),
        }

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        request = Request(
            self.base_url + "/api/chat", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        started = time.perf_counter()
        with self._opener(request, timeout=self.timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
        elapsed = max(0.0, time.perf_counter() - started)
        if not isinstance(raw, dict) or raw.get("model") != self.model_id:
            raise ValueError("Qwen tuning response model identity mismatch")
        return raw, elapsed

    def post_chat_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        """Post one already-constructed chat payload without changing it."""
        return self._post(payload)

    @staticmethod
    def _batch_messages(tasks: tuple[AtomicTask, ...]) -> list[dict[str, str]]:
        schema = '{"answers":[{"task_id":"TASK_ID","answer":VALUE}]}'
        lines = [
            "Execute each task independently. Return JSON only using this batch schema: " + schema,
            "Include exactly one entry per task_id and do not explain reasoning.",
        ]
        for task in tasks:
            lines.append(f"\nTASK {task.task_id}\n{task.prompt}")
        return [
            {"role": "system", "content": "Follow requested output contracts exactly and preserve task IDs."},
            {"role": "user", "content": "\n".join(lines)},
        ]

    @staticmethod
    def _direct_options(seed: int) -> dict[str, Any]:
        return {
            "temperature": 0.7, "top_p": 0.8, "top_k": 20,
            "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0,
            "seed": int(seed), "num_ctx": NUM_CTX, "num_predict": FINAL_MAX_TOKENS,
        }

    @staticmethod
    def _thinking_options(tasks: tuple[AtomicTask, ...], profile: Profile, seed: int) -> dict[str, Any]:
        precise = all(task.family in {"CODING_GENERATION", "DEBUGGING_REVIEW"} for task in tasks)
        return {
            "temperature": float(profile.temperature), "top_p": 0.95, "top_k": 20,
            "min_p": 0.0, "presence_penalty": 0.0 if precise else 1.5,
            "repeat_penalty": 1.0, "seed": int(seed), "num_ctx": NUM_CTX,
            "num_predict": int(profile.thinking_budget),
        }

    @staticmethod
    def _split_batch_response(text: str, tasks: tuple[AtomicTask, ...]) -> tuple[str, ...]:
        value = text.strip()
        if value.startswith("```") and value.endswith("```"):
            lines = value.splitlines()
            if len(lines) >= 3:
                value = "\n".join(lines[1:-1]).strip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return tuple(text for _ in tasks)

        if isinstance(parsed, dict) and isinstance(parsed.get("answers"), list):
            by_id = {}
            for item in parsed["answers"]:
                if isinstance(item, dict) and isinstance(item.get("task_id"), str):
                    by_id[item["task_id"]] = item
            responses = []
            for task in tasks:
                item = by_id.get(task.task_id)
                if not isinstance(item, dict):
                    responses.append(text)
                    continue
                payload = {key: val for key, val in item.items() if key != "task_id"}
                responses.append(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
            return tuple(responses)

        if isinstance(parsed, dict) and all(task.task_id in parsed for task in tasks):
            return tuple(
                json.dumps({"result": parsed[task.task_id]}, separators=(",", ":"), ensure_ascii=False)
                for task in tasks
            )
        if isinstance(parsed, list) and len(parsed) == len(tasks):
            return tuple(
                json.dumps(item if isinstance(item, dict) else {"result": item}, separators=(",", ":"), ensure_ascii=False)
                for item in parsed
            )
        return tuple(text for _ in tasks)

    def complete(self, tasks: tuple[AtomicTask, ...], profile: Profile, seed: int) -> AdapterCompletion:
        if not tasks:
            raise ValueError("Qwen batch requires tasks")
        messages = self._batch_messages(tasks)
        if not profile.thinking:
            request_payload = {
                "model": self.model_id, "messages": messages, "stream": False,
                "think": False, "options": self._direct_options(seed),
            }
            raw, elapsed = self._post(request_payload)
            content = str((raw.get("message") or {}).get("content") or "")
            return AdapterCompletion(
                responses=self._split_batch_response(content, tasks),
                latency_s=elapsed, output_tokens=int(raw.get("eval_count", 0) or 0),
                thinking_tokens=0, physical_calls=1,
                raw_calls=({"request": request_payload, "response": raw},),
            )

        first_request = {
            "model": self.model_id, "messages": messages, "stream": False,
            "think": True, "options": self._thinking_options(tasks, profile, seed),
        }
        first, first_elapsed = self._post(first_request)
        first_message = first.get("message") or {}
        thinking = str(first_message.get("thinking") or "")
        partial_content = str(first_message.get("content") or "")
        carried = messages + [
            {"role": "assistant", "thinking": thinking, "content": partial_content},
            {"role": "user", "content": "Using the reasoning above, return only the final JSON batch answer required by the original tasks."},
        ]
        second_request = {
            "model": self.model_id, "messages": carried, "stream": False,
            "think": False, "options": self._direct_options(seed),
        }
        second, second_elapsed = self._post(second_request)
        content = str((second.get("message") or {}).get("content") or "")
        first_tokens = int(first.get("eval_count", 0) or 0)
        second_tokens = int(second.get("eval_count", 0) or 0)
        return AdapterCompletion(
            responses=self._split_batch_response(content, tasks),
            latency_s=first_elapsed + second_elapsed,
            output_tokens=first_tokens + second_tokens,
            thinking_tokens=first_tokens, physical_calls=2,
            raw_calls=(
                {"request": first_request, "response": first},
                {"request": second_request, "response": second},
            ),
        )
