import json

from inverted.harvest_d.d4_qwen_policy import (
    QwenCompletionClass,
    classify_qwen_completion,
    select_qwen_policy,
)
from inverted.harvest_d.models import OllamaChatAdapter


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ollama_chat_adapter_sends_thinking_control_at_top_level():
    captured = {}

    def opener(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": "qwen", "message": {"content": '{"answer":"x"}'},
            "done": True, "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 5,
        })

    adapter = OllamaChatAdapter("qwen", opener=opener, chat_options={"think": False})
    adapter.complete("test")
    assert captured["think"] is False
    assert "think" not in captured["options"]


def test_default_adapter_request_does_not_change_when_chat_options_absent():
    captured = {}

    def opener(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": "qwen", "message": {"content": "ok"}, "done": True,
            "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 5,
        })

    OllamaChatAdapter("qwen", opener=opener).complete("test")
    assert "think" not in captured


def test_qwen_completion_classifies_context_exhaustion_and_empty_final():
    assert classify_qwen_completion(
        done_reason="length", input_tokens=100, output_tokens=3996, num_ctx=4096, final_text=""
    ) is QwenCompletionClass.CONTEXT_EXHAUSTED
    assert classify_qwen_completion(
        done_reason="stop", input_tokens=100, output_tokens=20, num_ctx=4096, final_text=""
    ) is QwenCompletionClass.EMPTY_FINAL
    assert classify_qwen_completion(
        done_reason="stop", input_tokens=100, output_tokens=20, num_ctx=4096, final_text='{"answer":"x"}'
    ) is QwenCompletionClass.SEMANTIC_RESULT


def _records(default_correct: list[bool], off_correct: list[bool], *, default_exhausted=None, off_exhausted=None):
    default_exhausted = default_exhausted or [False] * len(default_correct)
    off_exhausted = off_exhausted or [False] * len(off_correct)
    rows = []
    for index, (d_ok, o_ok) in enumerate(zip(default_correct, off_correct)):
        case_id = f"c{index:02d}"
        rows.append({
            "case_id": case_id, "policy_id": "DEFAULT", "semantic_action_correct": d_ok,
            "completion_class": "CONTEXT_EXHAUSTED" if default_exhausted[index] else "SEMANTIC_RESULT",
        })
        rows.append({
            "case_id": case_id, "policy_id": "THINK_OFF", "semantic_action_correct": o_ok,
            "completion_class": "CONTEXT_EXHAUSTED" if off_exhausted[index] else "SEMANTIC_RESULT",
        })
    return rows


def test_policy_selector_freezes_think_off_on_decisive_matched_semantic_gain():
    rows = _records([False] * 24, [True] * 24, default_exhausted=[True] * 24, off_exhausted=[False] * 24)
    result = select_qwen_policy(rows, model_id="qwen3.5:9b-q8_0")
    assert result["state"] == "FROZEN"
    assert result["policy_id"] == "THINK_OFF"
    assert result["chat_options"] == {"think": False}
    assert result["matched_cases"] == 24
    assert result["semantic_decision"] == "SUPERIOR"
    assert result["evidence_status"] == "DECISIVE"


def test_policy_selector_fixed_horizon_tie_freezes_default_without_superiority_claim():
    rows = _records([True, False] * 12, [True, False] * 12)
    result = select_qwen_policy(rows, model_id="qwen3.5:9b-q8_0")
    assert result["state"] == "FROZEN"
    assert result["policy_id"] == "DEFAULT"
    assert result["semantic_decision"] == "NO_DECISIVE_DIFFERENCE"
    assert result["evidence_status"] == "PROVISIONAL_FIXED_HORIZON"


def test_policy_selector_remains_incomplete_before_24_matched_cases():
    rows = _records([True] * 12, [True] * 12)
    result = select_qwen_policy(rows, model_id="qwen3.5:9b-q8_0")
    assert result["state"] == "UNRESOLVED"
    assert result["policy_id"] is None
    assert result["evidence_status"] == "INCOMPLETE"
