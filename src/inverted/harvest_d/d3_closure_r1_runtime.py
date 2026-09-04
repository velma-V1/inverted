from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, TextIO

from inverted.progress import InPlaceProgress

from .d3_closure_r1 import R1Plan
from .models import ModelResponse


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")
        handle.flush()


class R1RuntimeRecorder:
    """Observability-only wrapper for physical R1 calls.

    It records exact exposure/runtime payloads and renders progress, but never
    changes prompts, options, scheduling, retry policy, or scientific decisions.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        plan: R1Plan,
        committed_experiment_ids: set[str],
        target_calls: int,
        calls_available: int,
        progress_stream: TextIO | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.plan = plan
        self.committed = set(committed_experiment_ids)
        self.remaining = [row for row in plan.experiments if row.experiment_id not in self.committed]
        self.start_completed = len(self.committed)
        self.completed = self.start_completed
        self.target_calls = int(target_calls)
        self.calls_available = int(calls_available)
        if self.start_completed > self.target_calls:
            raise ValueError("R1 progress state exceeds requested target")
        self.progress = InPlaceProgress(
            stream=progress_stream,
            min_interval_s=0.0,
            initial_completed=self.start_completed,
        )
        self.progress.update(
            completed=self.completed,
            total=max(1, self.target_calls),
            current="R1 calibration",
            calls_used=self.completed,
            calls_available=self.calls_available,
            force=True,
        )

    def wrap(self, model_key: str, adapter: Any) -> "_RecordingAdapter":
        return _RecordingAdapter(self, str(model_key), adapter)

    def _next_experiment(self, model_key: str):
        index = self.completed - self.start_completed
        if index < 0 or index >= len(self.remaining):
            raise ValueError("R1 runtime recorder has no matching planned experiment")
        experiment = self.remaining[index]
        if experiment.model_key != model_key:
            raise ValueError(
                f"R1 runtime call order mismatch: expected {experiment.model_key}, observed {model_key}"
            )
        return experiment

    def _request_row(self, model_key: str, adapter: Any, prompt: str, system: str | None) -> tuple[Any, dict[str, Any]]:
        experiment = self._next_experiment(model_key)
        physical_id = f"r1-call:{experiment.experiment_id}"
        row = {
            "physical_model_call_id": physical_id,
            "experiment_id": experiment.experiment_id,
            "stage": experiment.stage,
            "model_key": experiment.model_key,
            "case_id": experiment.case_id,
            "family": experiment.family,
            "repeat_index": experiment.repeat_index,
            "sentinel": experiment.sentinel,
            "system": system,
            "prompt": prompt,
            "system_sha256": _sha256_text(system or ""),
            "prompt_sha256": _sha256_text(prompt),
            "model_id": str(getattr(adapter, "model_id", "unknown")),
            "generation_options": dict(getattr(adapter, "generation_options", {}) or {}),
            "chat_options": dict(getattr(adapter, "chat_options", {}) or {}),
            "attempt": 1,
        }
        _append_jsonl(self.root / "closure_r1_raw_model_requests.jsonl", row)
        return experiment, row

    def _record_success(self, request: Mapping[str, Any], response: ModelResponse) -> None:
        payload = dict(response.raw or {})
        base = {
            "physical_model_call_id": request["physical_model_call_id"],
            "experiment_id": request["experiment_id"],
            "model_key": request["model_key"],
            "model_id": response.model,
        }
        _append_jsonl(self.root / "closure_r1_raw_model_responses.jsonl", {
            **base,
            "text": response.text,
            "payload": payload,
        })
        _append_jsonl(self.root / "closure_r1_runtime_telemetry.jsonl", {
            **base,
            "done_reason": payload.get("done_reason"),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "total_duration_ns": payload.get("total_duration"),
            "load_duration_ns": payload.get("load_duration"),
            "prompt_eval_duration_ns": payload.get("prompt_eval_duration"),
            "eval_duration_ns": payload.get("eval_duration"),
            "prompt_eval_count": payload.get("prompt_eval_count", response.input_tokens),
            "eval_count": payload.get("eval_count", response.output_tokens),
            "completion_class": "OBSERVED_RESPONSE",
        })

    def _record_error(self, request: Mapping[str, Any], exc: Exception) -> None:
        base = {
            "physical_model_call_id": request["physical_model_call_id"],
            "experiment_id": request["experiment_id"],
            "model_key": request["model_key"],
            "model_id": request["model_id"],
        }
        _append_jsonl(self.root / "closure_r1_raw_model_responses.jsonl", {
            **base,
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        _append_jsonl(self.root / "closure_r1_runtime_telemetry.jsonl", {
            **base,
            "done_reason": "ERROR",
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0.0,
            "total_duration_ns": None,
            "load_duration_ns": None,
            "prompt_eval_duration_ns": None,
            "eval_duration_ns": None,
            "prompt_eval_count": 0,
            "eval_count": 0,
            "completion_class": "INFRASTRUCTURE_OR_ADAPTER",
            "error_type": type(exc).__name__,
        })

    def _advance(self, experiment: Any) -> None:
        self.completed += 1
        self.progress.update(
            completed=min(self.completed, max(1, self.target_calls)),
            total=max(1, self.target_calls),
            current=f"R1 {experiment.model_key} {experiment.family}",
            calls_used=self.completed,
            calls_available=self.calls_available,
            force=True,
        )

    def finish(self) -> None:
        self.progress.finish()


class _RecordingAdapter:
    def __init__(self, recorder: R1RuntimeRecorder, model_key: str, delegate: Any) -> None:
        self._recorder = recorder
        self._model_key = model_key
        self._delegate = delegate
        self.model_id = getattr(delegate, "model_id", "unknown")
        self.generation_options = dict(getattr(delegate, "generation_options", {}) or {})
        self.chat_options = dict(getattr(delegate, "chat_options", {}) or {})

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        experiment, request = self._recorder._request_row(self._model_key, self._delegate, prompt, system)
        try:
            response = self._delegate.complete(prompt, system=system)
        except Exception as exc:
            self._recorder._record_error(request, exc)
            self._recorder._advance(experiment)
            raise
        self._recorder._record_success(request, response)
        self._recorder._advance(experiment)
        return response
