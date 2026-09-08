from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

import pytest

import inverted.capability_ratchet as ratchet
from inverted.capability_ratchet import AttemptEvidence, AttemptOutcome, RetryIngredient
from inverted.capability_ratchet.orchestration import AttemptContext
from inverted.universal_tuning.core import AtomicTask, Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


MODEL_ID = "qwen3.5:9b-q8_0"
ORACLE_SECRET = "ORACLE_ONLY_DO_NOT_SEND"
PRIOR_ANSWER = '{"answer":"A","private_marker":"PRIOR_STATE"}'


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


def _executor_cls():
    assert hasattr(ratchet, "QwenRetryAttemptExecutor"), (
        "Test1B-v3 requires a public QwenRetryAttemptExecutor that turns retry "
        "ingredients into the exact Ollama requests captured as attempt evidence"
    )
    return ratchet.QwenRetryAttemptExecutor


def _task() -> AtomicTask:
    return AtomicTask(
        task_id="qwen-retry-d4",
        family="LOGIC",
        difficulty=4,
        prompt="Return the only valid assignment as an answer object.",
        expected={"answer": "B"},
        scorer="exact_value",
        contract="answer_object",
    )


def _base_profile(*, thinking_budget: int = 0) -> Profile:
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


def _previous_failure() -> AttemptOutcome:
    previous_request = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": "prior system"},
            {"role": "user", "content": _task().prompt},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7, "seed": 444, "num_predict": 222},
    }
    previous_response = {
        "model": MODEL_ID,
        "message": {"role": "assistant", "content": PRIOR_ANSWER},
        "eval_count": 13,
    }
    evidence = AttemptEvidence(
        request_envelopes=(previous_request,),
        forensic_payload={
            "raw_calls": ({"request": previous_request, "response": previous_response},),
            "telemetry": {"latency_s": 1.4, "output_tokens": 13, "thinking_tokens": 0},
        },
        oracle_payload={
            "task_id": _task().task_id,
            "expected": {"answer": ORACLE_SECRET},
            "contract": "answer_object",
            "scorer": "exact_value",
            "score": {
                "completed": True,
                "semantic_pass": False,
                "contract_pass": True,
                "semantic_quality": 0.0,
                "contract_quality": 1.0,
                "reason": "SEMANTIC_FAIL",
                "normalized_answer": ORACLE_SECRET,
            },
            "unsafe_validator_detail": ORACLE_SECRET,
        },
        inference_profile=asdict(_base_profile()),
        inference_seed=444,
        source_evidence_refs=("attempt:INITIAL",),
    )
    return AttemptOutcome(
        passed=False,
        failure_classes=("SEMANTIC_FAIL",),
        failure_subtypes=("WRONG_ASSIGNMENT",),
        evidence=evidence,
    )


def _retry_context(ingredient: RetryIngredient) -> AttemptContext:
    return AttemptContext(
        model_id=MODEL_ID,
        task=_task(),
        stage="RETRY_A",
        attempt_index=1,
        retry_ingredient=ingredient,
        previous_outcome=_previous_failure(),
    )


def test_preserve_class_only_repair_changes_the_physical_qwen_request() -> None:
    payloads: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": MODEL_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 7,
        })

    ingredient = RetryIngredient(
        "retry-a",
        "preserve-state-minimal-diagnostic",
        context_mode="PRESERVE",
        failure_feedback_mode="CLASS_ONLY",
        response_mode="REPAIR",
        instruction="Repair only the failed constraint; preserve valid work.",
        profile_overrides={"temperature": 0.2, "top_p": 0.91},
    )
    executor = _executor_cls()(
        adapter=QwenOllamaAdapter(opener=opener),
        base_profile=_base_profile(),
        seed=444,
    )

    outcome = executor(_retry_context(ingredient))

    assert outcome.passed is True
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["options"]["temperature"] == 0.2
    assert payload["options"]["top_p"] == 0.91
    assert payload["options"]["top_k"] == 37
    messages = payload["messages"]
    assert any(message.get("role") == "assistant" and message.get("content") == PRIOR_ANSWER for message in messages)
    retry_text = "\n".join(str(message.get("content", "")) for message in messages if message.get("role") == "user")
    assert "SEMANTIC_FAIL" in retry_text
    assert "Repair only the failed constraint; preserve valid work." in retry_text
    assert ORACLE_SECRET not in json.dumps(payload)
    assert _plain(outcome.evidence.request_envelopes) == payloads
    assert outcome.evidence.inference_profile["temperature"] == 0.2
    assert outcome.evidence.inference_profile["top_p"] == 0.91


def test_fresh_validator_regenerate_excludes_prior_state_and_oracle_answers() -> None:
    payloads: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": MODEL_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 8,
        })

    ingredient = RetryIngredient(
        "retry-b",
        "fresh-context-validator-evidence",
        context_mode="FRESH",
        failure_feedback_mode="VALIDATOR_EVIDENCE",
        response_mode="REGENERATE",
        instruction="Reconstruct from scratch using only the validator evidence.",
        profile_overrides={"temperature": 0.45},
    )
    context = AttemptContext(
        model_id=MODEL_ID,
        task=_task(),
        stage="RETRY_B",
        attempt_index=2,
        retry_ingredient=ingredient,
        previous_outcome=_previous_failure(),
    )
    executor = _executor_cls()(
        adapter=QwenOllamaAdapter(opener=opener),
        base_profile=_base_profile(),
        seed=445,
    )

    outcome = executor(context)

    payload = payloads[0]
    serialized = json.dumps(payload, sort_keys=True)
    assert PRIOR_ANSWER not in serialized
    assert "PRIOR_STATE" not in serialized
    assert ORACLE_SECRET not in serialized
    assert not any(message.get("role") == "assistant" for message in payload["messages"])
    feedback = "\n".join(str(message.get("content", "")) for message in payload["messages"])
    assert "semantic_pass" in feedback
    assert "contract_pass" in feedback
    assert "SEMANTIC_FAIL" in feedback
    assert "WRONG_ASSIGNMENT" in feedback
    assert "Reconstruct from scratch using only the validator evidence." in feedback
    assert outcome.evidence.inference_profile["temperature"] == 0.45


def test_thinking_retry_evidence_is_exactly_the_two_physical_calls_and_exposed_ollama_thinking() -> None:
    payloads: list[dict[str, Any]] = []
    responses = iter((
        {
            "model": MODEL_ID,
            "message": {
                "role": "assistant",
                "thinking": "EXPOSED_OLLAMA_THINKING",
                "content": "",
            },
            "eval_count": 64,
        },
        {
            "model": MODEL_ID,
            "message": {"role": "assistant", "content": '{"answer":"B"}'},
            "eval_count": 6,
        },
    ))

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response(next(responses))

    executor = _executor_cls()(
        adapter=QwenOllamaAdapter(opener=opener),
        base_profile=_base_profile(thinking_budget=64),
        seed=446,
    )
    context = AttemptContext(
        model_id=MODEL_ID,
        task=_task(),
        stage="INITIAL",
        attempt_index=0,
        retry_ingredient=None,
        previous_outcome=None,
    )

    outcome = executor(context)

    assert outcome.passed is True
    assert len(payloads) == 2
    assert payloads[0]["think"] is True
    assert payloads[0]["options"]["num_predict"] == 64
    assert payloads[1]["think"] is False
    assert payloads[1]["options"]["num_predict"] == 222
    assert _plain(outcome.evidence.request_envelopes) == payloads
    raw_calls = outcome.evidence.forensic_payload["raw_calls"]
    assert _plain(tuple(call["request"] for call in raw_calls)) == payloads
    assert raw_calls[0]["response"]["message"]["thinking"] == "EXPOSED_OLLAMA_THINKING"
    assert outcome.evidence.forensic_payload["telemetry"]["thinking_tokens"] == 64
    assert "chain_of_thought" not in repr(outcome.evidence.forensic_payload)


def test_unknown_retry_profile_override_is_rejected_before_any_model_call() -> None:
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        calls += 1
        raise AssertionError("unknown override must fail before an Ollama request")

    ingredient = RetryIngredient(
        "retry-invalid",
        "unknown-profile-field",
        profile_overrides={"not_a_profile_field": 123},
    )
    executor = _executor_cls()(
        adapter=QwenOllamaAdapter(opener=opener),
        base_profile=_base_profile(),
        seed=447,
    )

    with pytest.raises(ValueError, match="not_a_profile_field"):
        executor(_retry_context(ingredient))

    assert calls == 0
