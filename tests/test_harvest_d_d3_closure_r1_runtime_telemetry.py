from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

from inverted.harvest_d.d3_closure_r1 import R1Experiment, R1Plan
from inverted.harvest_d.d3_closure_r1_runtime import R1RuntimeRecorder
from inverted.harvest_d.models import ModelResponse


class _Adapter:
    model_id = "small:test"
    generation_options = {"temperature": 0.0, "seed": 7, "num_ctx": 4096}
    chat_options = {}

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        return ModelResponse(
            '{"answer":"ok"}',
            self.model_id,
            17,
            3,
            12.5,
            {
                "done_reason": "stop",
                "total_duration": 12000000,
                "load_duration": 2000000,
                "prompt_eval_duration": 3000000,
                "eval_duration": 7000000,
                "prompt_eval_count": 17,
                "eval_count": 3,
            },
        )


def _plan() -> R1Plan:
    return R1Plan((R1Experiment(
        experiment_id="R1:SMALL_A:case-1:R1",
        stage="R1_CALIBRATION",
        model_key="SMALL_A",
        case_id="case-1",
        family="STATE",
        repeat_index=1,
        sentinel=True,
    ),))


def _read_one(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8").strip())


def test_r1_runtime_recorder_preserves_raw_request_response_and_duration_telemetry(tmp_path: Path):
    stream = StringIO()
    recorder = R1RuntimeRecorder(
        tmp_path,
        plan=_plan(),
        committed_experiment_ids=set(),
        target_calls=1,
        calls_available=24,
        progress_stream=stream,
    )
    adapter = recorder.wrap("SMALL_A", _Adapter())
    response = adapter.complete("hello", system="system")
    recorder.finish()

    assert response.text == '{"answer":"ok"}'
    request = _read_one(tmp_path / "closure_r1_raw_model_requests.jsonl")
    raw = _read_one(tmp_path / "closure_r1_raw_model_responses.jsonl")
    runtime = _read_one(tmp_path / "closure_r1_runtime_telemetry.jsonl")

    assert request["experiment_id"] == "R1:SMALL_A:case-1:R1"
    assert request["system"] == "system"
    assert request["prompt"] == "hello"
    assert request["generation_options"]["num_ctx"] == 4096
    assert request["prompt_sha256"] and request["system_sha256"]
    assert raw["payload"]["load_duration"] == 2000000
    assert runtime["load_duration_ns"] == 2000000
    assert runtime["total_duration_ns"] == 12000000
    assert runtime["prompt_eval_duration_ns"] == 3000000
    assert runtime["eval_duration_ns"] == 7000000
    assert runtime["input_tokens"] == 17
    assert runtime["output_tokens"] == 3
    assert "R1" in stream.getvalue()


def test_r1_runtime_recorder_marks_physical_identity_stably(tmp_path: Path):
    recorder = R1RuntimeRecorder(
        tmp_path,
        plan=_plan(),
        committed_experiment_ids=set(),
        target_calls=1,
        calls_available=24,
    )
    recorder.wrap("SMALL_A", _Adapter()).complete("hello", system="system")
    recorder.finish()
    request = _read_one(tmp_path / "closure_r1_raw_model_requests.jsonl")
    raw = _read_one(tmp_path / "closure_r1_raw_model_responses.jsonl")
    assert request["physical_model_call_id"] == raw["physical_model_call_id"]
    assert request["physical_model_call_id"].startswith("r1-call:")
