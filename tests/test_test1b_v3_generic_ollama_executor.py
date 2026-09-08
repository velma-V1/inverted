from __future__ import annotations

import json
from typing import Any

import pytest

import inverted.capability_ratchet as ratchet
from inverted.capability_ratchet.orchestration import AttemptContext
from inverted.universal_tuning.core import AtomicTask, Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


DEVSTRAL_ID = "devstral-small-2:24b"
QWEN_ID = "qwen3.5:9b-q8_0"


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _api():
    assert hasattr(ratchet, "OllamaExecutionCapabilities")
    assert hasattr(ratchet, "OllamaRetryAttemptExecutor")
    return ratchet.OllamaExecutionCapabilities, ratchet.OllamaRetryAttemptExecutor


def _task() -> AtomicTask:
    return AtomicTask(
        task_id="generic-ollama-d3",
        family="LOGIC",
        difficulty=3,
        prompt="Return the exact answer object.",
        expected="B",
        scorer="exact_value",
        contract="answer_object",
    )


def _context(model_id: str) -> AttemptContext:
    return AttemptContext(
        model_id=model_id,
        task=_task(),
        stage="INITIAL",
        attempt_index=0,
        retry_ingredient=None,
        previous_outcome=None,
    )


def _profile(*, thinking_budget: int = 0) -> Profile:
    return Profile(
        thinking_budget=thinking_budget,
        temperature=0.4,
        top_p=0.9,
        top_k=32,
        num_ctx=8192,
        final_max_tokens=192,
    )


def test_direct_only_model_uses_same_evidence_path_without_qwen_think_control() -> None:
    Capabilities, Executor = _api()
    payloads: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": DEVSTRAL_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 7,
        })

    executor = Executor(
        adapter=QwenOllamaAdapter(model_id=DEVSTRAL_ID, opener=opener),
        base_profile=_profile(),
        seed=701,
        capabilities=Capabilities(thinking_mode="NONE"),
    )
    outcome = executor(_context(DEVSTRAL_ID))

    assert outcome.passed is True
    assert len(payloads) == 1
    assert "think" not in payloads[0]
    assert payloads[0]["model"] == DEVSTRAL_ID
    assert outcome.evidence.request_envelopes[0]["model"] == DEVSTRAL_ID
    assert outcome.evidence.forensic_payload["telemetry"]["physical_calls"] == 1
    assert outcome.evidence.source_evidence_refs == (
        f"test1b-v3:{DEVSTRAL_ID}:{_task().task_id}:INITIAL",
    )


def test_direct_only_model_rejects_positive_thinking_budget_before_physical_call() -> None:
    Capabilities, Executor = _api()
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        calls += 1
        raise AssertionError("unsupported thinking must fail before transport")

    executor = Executor(
        adapter=QwenOllamaAdapter(model_id=DEVSTRAL_ID, opener=opener),
        base_profile=_profile(thinking_budget=256),
        seed=702,
        capabilities=Capabilities(thinking_mode="NONE"),
    )

    with pytest.raises(ValueError, match="thinking"):
        executor(_context(DEVSTRAL_ID))
    assert calls == 0


def test_ollama_thinking_capability_preserves_two_stage_qwen_execution() -> None:
    Capabilities, Executor = _api()
    payloads: list[dict[str, Any]] = []
    responses = iter((
        {
            "model": QWEN_ID,
            "message": {"role": "assistant", "thinking": "bounded", "content": ""},
            "eval_count": 64,
        },
        {
            "model": QWEN_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 5,
        },
    ))

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response(next(responses))

    executor = Executor(
        adapter=QwenOllamaAdapter(model_id=QWEN_ID, opener=opener),
        base_profile=_profile(thinking_budget=64),
        seed=703,
        capabilities=Capabilities(thinking_mode="OLLAMA"),
    )
    outcome = executor(_context(QWEN_ID))

    assert outcome.passed is True
    assert len(payloads) == 2
    assert payloads[0]["think"] is True
    assert payloads[0]["options"]["num_predict"] == 64
    assert payloads[1]["think"] is False
    assert payloads[1]["options"]["num_predict"] == 192
    assert outcome.evidence.forensic_payload["telemetry"]["thinking_tokens"] == 64
    assert outcome.evidence.forensic_payload["telemetry"]["physical_calls"] == 2


def test_transport_failure_normalization_is_model_generic() -> None:
    Capabilities, Executor = _api()

    def opener(request, *, timeout):
        raise ConnectionError("devstral transport unavailable")

    executor = Executor(
        adapter=QwenOllamaAdapter(model_id=DEVSTRAL_ID, opener=opener),
        base_profile=_profile(),
        seed=704,
        capabilities=Capabilities(thinking_mode="NONE"),
    )
    outcome = executor(_context(DEVSTRAL_ID))

    assert outcome.passed is False
    assert outcome.failure_classes == ("TRANSPORT",)
    assert outcome.evidence.forensic_payload["execution_error"]["type"] == "ConnectionError"
    assert outcome.evidence.request_envelopes[0]["model"] == DEVSTRAL_ID
    assert "think" not in outcome.evidence.request_envelopes[0]


def test_qwen_executor_remains_backward_compatible_wrapper() -> None:
    assert hasattr(ratchet, "QwenRetryAttemptExecutor")
    payloads: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": QWEN_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 5,
        })

    executor = ratchet.QwenRetryAttemptExecutor(
        adapter=QwenOllamaAdapter(model_id=QWEN_ID, opener=opener),
        base_profile=_profile(),
        seed=705,
    )
    outcome = executor(_context(QWEN_ID))

    assert outcome.passed is True
    assert payloads[0]["think"] is False


def test_capabilities_reject_unknown_thinking_mode() -> None:
    Capabilities, _ = _api()
    with pytest.raises(ValueError, match="thinking_mode"):
        Capabilities(thinking_mode="MAGIC")
