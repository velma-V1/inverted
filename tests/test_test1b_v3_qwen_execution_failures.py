from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import URLError

from inverted.capability_ratchet import QwenRetryAttemptExecutor, RetryCampaignOrchestrator, RetryIngredient
from inverted.capability_ratchet.orchestration import AttemptContext
from inverted.universal_tuning.core import AtomicTask, Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


MODEL_ID = "qwen3.5:9b-q8_0"


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _task(task_id: str = "qwen-exec-d5") -> AtomicTask:
    return AtomicTask(
        task_id=task_id,
        family="LOGIC",
        difficulty=5,
        prompt="Return the only valid assignment as an answer object.",
        expected="B",
        scorer="exact_value",
        contract="answer_object",
    )


def _profile(*, thinking_budget: int = 0) -> Profile:
    return Profile(
        thinking_budget=thinking_budget,
        temperature=0.7,
        top_p=0.81,
        top_k=37,
        min_p=0.04,
        repeat_penalty=1.06,
        num_ctx=12288,
        final_max_tokens=222,
    )


def _initial(task: AtomicTask | None = None) -> AttemptContext:
    return AttemptContext(
        model_id=MODEL_ID,
        task=task or _task(),
        stage="INITIAL",
        attempt_index=0,
        retry_ingredient=None,
        previous_outcome=None,
    )


def _executor(opener, *, thinking_budget: int = 0) -> QwenRetryAttemptExecutor:
    return QwenRetryAttemptExecutor(
        adapter=QwenOllamaAdapter(opener=opener),
        base_profile=_profile(thinking_budget=thinking_budget),
        seed=501,
    )


def test_first_call_timeout_becomes_evidence_bearing_failed_outcome() -> None:
    posted: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        posted.append(json.loads(request.data.decode("utf-8")))
        raise TimeoutError("ollama generation timed out")

    outcome = _executor(opener)(_initial())

    assert outcome.passed is False
    assert outcome.failure_classes == ("TIMEOUT",)
    assert len(posted) == 1
    assert _plain(outcome.evidence.request_envelopes) == posted
    assert outcome.evidence.forensic_payload["telemetry"]["physical_calls"] == 1
    raw_calls = outcome.evidence.forensic_payload["raw_calls"]
    assert len(raw_calls) == 1
    assert _plain(raw_calls[0]["request"]) == posted[0]
    assert raw_calls[0]["error"]["class"] == "TIMEOUT"
    assert raw_calls[0]["error"]["type"] == "TimeoutError"
    assert "timed out" in raw_calls[0]["error"]["message"]
    assert outcome.evidence.forensic_payload["execution_error"]["class"] == "TIMEOUT"


def test_transport_failure_becomes_replayable_without_escaping() -> None:
    posted: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        posted.append(json.loads(request.data.decode("utf-8")))
        raise URLError("connection refused")

    outcome = _executor(opener)(_initial())

    assert outcome.passed is False
    assert outcome.failure_classes == ("TRANSPORT",)
    assert _plain(outcome.evidence.request_envelopes) == posted
    assert outcome.evidence.forensic_payload["telemetry"]["physical_calls"] == 1
    raw_call = outcome.evidence.forensic_payload["raw_calls"][0]
    assert raw_call["error"]["class"] == "TRANSPORT"
    assert raw_call["error"]["type"] == "URLError"
    assert "connection refused" in raw_call["error"]["message"]


def test_malformed_successful_http_response_preserves_raw_response_and_normalizes_failure() -> None:
    posted: list[dict[str, Any]] = []
    malformed = {
        "model": MODEL_ID,
        "message": "not-a-message-object",
        "eval_count": 3,
    }

    def opener(request, *, timeout):
        posted.append(json.loads(request.data.decode("utf-8")))
        return _Response(malformed)

    outcome = _executor(opener)(_initial())

    assert outcome.passed is False
    assert outcome.failure_classes == ("MALFORMED_RESPONSE",)
    assert _plain(outcome.evidence.request_envelopes) == posted
    raw_call = outcome.evidence.forensic_payload["raw_calls"][0]
    assert _plain(raw_call["response"]) == malformed
    assert raw_call["error"]["class"] == "MALFORMED_RESPONSE"
    assert outcome.evidence.forensic_payload["execution_error"]["class"] == "MALFORMED_RESPONSE"
    assert outcome.evidence.forensic_payload["telemetry"]["physical_calls"] == 1


def test_second_stage_thinking_timeout_preserves_first_stage_and_second_attempted_request() -> None:
    posted: list[dict[str, Any]] = []
    calls = 0
    first_response = {
        "model": MODEL_ID,
        "message": {
            "role": "assistant",
            "thinking": "EXPOSED_THINKING_BEFORE_TIMEOUT",
            "content": "",
        },
        "eval_count": 64,
    }

    def opener(request, *, timeout):
        nonlocal calls
        calls += 1
        posted.append(json.loads(request.data.decode("utf-8")))
        if calls == 1:
            return _Response(first_response)
        raise TimeoutError("finalization timed out")

    outcome = _executor(opener, thinking_budget=64)(_initial())

    assert outcome.passed is False
    assert outcome.failure_classes == ("TIMEOUT",)
    assert len(posted) == 2
    assert _plain(outcome.evidence.request_envelopes) == posted
    raw_calls = outcome.evidence.forensic_payload["raw_calls"]
    assert len(raw_calls) == 2
    assert _plain(raw_calls[0]["response"]) == first_response
    assert raw_calls[0]["response"]["message"]["thinking"] == "EXPOSED_THINKING_BEFORE_TIMEOUT"
    assert raw_calls[1]["error"]["class"] == "TIMEOUT"
    assert _plain(raw_calls[1]["request"]) == posted[1]
    telemetry = outcome.evidence.forensic_payload["telemetry"]
    assert telemetry["physical_calls"] == 2
    assert telemetry["thinking_tokens"] == 64
    assert telemetry["output_tokens"] == 64


def test_timeout_is_snapshotted_retry_a_recovers_and_campaign_continues_to_next_task() -> None:
    posted: list[dict[str, Any]] = []
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        calls += 1
        posted.append(json.loads(request.data.decode("utf-8")))
        if calls == 1:
            raise TimeoutError("first task initial timeout")
        return _Response({
            "model": MODEL_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 5,
        })

    executor = _executor(opener)
    snapshots: list[tuple[str, str, tuple[str, ...], int]] = []

    def snapshot_failure(context, outcome):
        snapshots.append((
            context.task.task_id,
            context.stage,
            outcome.failure_classes,
            outcome.evidence.forensic_payload["telemetry"]["physical_calls"],
        ))
        return f"snapshot-{len(snapshots)}"

    orchestrator = RetryCampaignOrchestrator(
        execute_attempt=executor,
        snapshot_failure=snapshot_failure,
        retry_a=RetryIngredient(
            "retry-a",
            "fresh retry after execution failure",
            context_mode="FRESH",
            failure_feedback_mode="CLASS_ONLY",
            response_mode="REGENERATE",
        ),
        retry_b=RetryIngredient(
            "retry-b",
            "alternate fresh retry",
            context_mode="FRESH",
            failure_feedback_mode="GENERIC",
            response_mode="REGENERATE",
        ),
    )

    result = orchestrator.run(model_id=MODEL_ID, tasks=(_task("task-1"), _task("task-2")))

    assert snapshots == [("task-1", "INITIAL", ("TIMEOUT",), 1)]
    assert result.task_results[0].status == "RECOVERED_RETRY_A"
    assert result.task_results[0].attempt_count == 2
    assert result.task_results[1].status == "FIRST_SHOT_PASS"
    assert result.task_results[1].attempt_count == 1
    assert len(posted) == 3
