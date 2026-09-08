from __future__ import annotations

import json
from typing import Any

from inverted.universal_tuning.core import AtomicTask, Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _task() -> AtomicTask:
    return AtomicTask(
        task_id="profile-contract",
        family="TEST1B_V3",
        difficulty=4,
        prompt="Return the exact requested JSON answer.",
        expected={"answer": 4},
        scorer="exact_value",
    )


def _full_profile(*, thinking_budget: int) -> Profile:
    return Profile(
        thinking_budget=thinking_budget,
        temperature=0.31,
        top_p=0.77,
        top_k=41,
        min_p=0.06,
        typical_p=0.93,
        repeat_last_n=96,
        repeat_penalty=1.13,
        presence_penalty=0.2,
        frequency_penalty=0.4,
        num_keep=32,
        num_ctx=12288,
        num_batch=256,
        num_gpu=33,
        main_gpu=0,
        use_mmap=True,
        num_thread=8,
        draft_num_predict=17,
        final_max_tokens=333,
        stop=("<END>", "<STOP>"),
        truncate=False,
        shift=True,
        logprobs=True,
        top_logprobs=5,
    )


def _expected_options(*, seed: int, num_predict: int) -> dict[str, Any]:
    return {
        "num_keep": 32,
        "seed": seed,
        "num_predict": num_predict,
        "top_k": 41,
        "top_p": 0.77,
        "min_p": 0.06,
        "typical_p": 0.93,
        "repeat_last_n": 96,
        "temperature": 0.31,
        "repeat_penalty": 1.13,
        "presence_penalty": 0.2,
        "frequency_penalty": 0.4,
        "stop": ["<END>", "<STOP>"],
        "num_ctx": 12288,
        "num_batch": 256,
        "num_gpu": 33,
        "main_gpu": 0,
        "use_mmap": True,
        "num_thread": 8,
        "draft_num_predict": 17,
    }


def _assert_request_controls(payload: dict[str, Any]) -> None:
    assert payload["truncate"] is False
    assert payload["shift"] is True
    assert payload["logprobs"] is True
    assert payload["top_logprobs"] == 5


def test_direct_qwen_request_uses_complete_explicit_inference_profile() -> None:
    payloads: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": "qwen3.5:9b-q8_0",
            "message": {"content": '{"answer":4}'},
            "eval_count": 5,
        })

    adapter = QwenOllamaAdapter(opener=opener)
    result = adapter.complete((_task(),), _full_profile(thinking_budget=0), seed=2468)

    assert result.physical_calls == 1
    assert len(payloads) == 1
    assert payloads[0]["think"] is False
    assert payloads[0]["options"] == _expected_options(seed=2468, num_predict=333)
    _assert_request_controls(payloads[0])


def test_bounded_thinking_uses_profile_for_both_calls_and_only_changes_token_ceiling() -> None:
    payloads: list[dict[str, Any]] = []
    responses = iter((
        {
            "model": "qwen3.5:9b-q8_0",
            "message": {"thinking": "bounded reasoning", "content": ""},
            "eval_count": 128,
        },
        {
            "model": "qwen3.5:9b-q8_0",
            "message": {"content": '{"answer":4}'},
            "eval_count": 5,
        },
    ))

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response(next(responses))

    adapter = QwenOllamaAdapter(opener=opener)
    result = adapter.complete((_task(),), _full_profile(thinking_budget=128), seed=2468)

    assert result.physical_calls == 2
    assert payloads[0]["think"] is True
    assert payloads[0]["options"] == _expected_options(seed=2468, num_predict=128)
    assert payloads[1]["think"] is False
    assert payloads[1]["options"] == _expected_options(seed=2468, num_predict=333)
    _assert_request_controls(payloads[0])
    _assert_request_controls(payloads[1])
    assert any(message.get("thinking") == "bounded reasoning" for message in payloads[1]["messages"])


def test_profile_defaults_remain_backward_compatible_for_existing_callers() -> None:
    profile = Profile(thinking_budget=512, temperature=0.6)

    assert profile.top_p is None
    assert profile.top_k is None
    assert profile.min_p is None
    assert profile.presence_penalty is None
    assert profile.repeat_penalty is None
    assert profile.final_max_tokens == 768
    assert profile.num_ctx == 8192
    assert profile.stop == ()
