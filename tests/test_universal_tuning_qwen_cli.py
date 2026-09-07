import json
import subprocess
from pathlib import Path

from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.scoring import score_atomic_task
from inverted.universal_tuning.tasks import build_qwen_task_pool
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


class _Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _tasks():
    pool = build_qwen_task_pool(seed=12, per_family=120)
    return tuple(task for task in pool.tasks if task.family == "EXTRACTION")[:5]


def _batch_content(tasks, key="answer"):
    return json.dumps({"answers": [
        {"task_id": task.task_id, key: task.expected} for task in tasks
    ]})


def test_direct_batch_uses_qwen_instruct_sampling_and_scheduler_seed():
    tasks = _tasks()
    payloads = []
    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": "qwen3.5:9b-q8_0",
            "message": {"content": _batch_content(tasks)},
            "eval_count": 45, "done_reason": "stop",
        })
    adapter = QwenOllamaAdapter(opener=opener)
    result = adapter.complete(tasks, Profile(0, 0.7), seed=12345)
    assert result.physical_calls == 1
    assert result.thinking_tokens == 0
    assert len(result.responses) == 5
    request = payloads[0]
    assert request["think"] is False
    assert request["options"]["temperature"] == 0.7
    assert request["options"]["top_p"] == 0.8
    assert request["options"]["top_k"] == 20
    assert request["options"]["seed"] == 12345
    assert all(task.task_id in request["messages"][1]["content"] for task in tasks)


def test_bounded_batch_preserves_reasoning_and_captures_natural_tokens():
    tasks = _tasks()
    payloads = []
    responses = iter([
        {"model":"qwen3.5:9b-q8_0", "message":{"thinking":"reasoning","content":""},
         "eval_count":137, "done_reason":"stop"},
        {"model":"qwen3.5:9b-q8_0", "message":{"content":_batch_content(tasks)},
         "eval_count":31, "done_reason":"stop"},
    ])
    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response(next(responses))
    adapter = QwenOllamaAdapter(opener=opener)
    result = adapter.complete(tasks, Profile(512, 0.6), seed=77)
    assert result.physical_calls == 2
    assert result.thinking_tokens == 137
    assert result.output_tokens == 168
    assert payloads[0]["think"] is True
    assert payloads[0]["options"]["num_predict"] == 512
    assert payloads[0]["options"]["temperature"] == 0.6
    assert payloads[0]["options"]["seed"] == 77
    assert payloads[1]["think"] is False
    assert any(m.get("thinking") == "reasoning" for m in payloads[1]["messages"])


def test_wrong_per_task_key_is_not_sanitized_into_contract_pass():
    tasks = _tasks()
    adapter = QwenOllamaAdapter(opener=lambda request, *, timeout: _Response({
        "model":"qwen3.5:9b-q8_0", "message":{"content":_batch_content(tasks, key="result")},
        "eval_count":40, "done_reason":"stop",
    }))
    result = adapter.complete(tasks, Profile(0, 0.7), seed=5)
    score = score_atomic_task(tasks[0], result.responses[0])
    assert score.semantic_pass is True
    assert score.contract_pass is False


def test_runtime_provenance_binds_exact_ollama_model_digest():
    responses = iter([
        {"version":"0.32.15"},
        {"models":[{"name":"qwen3.5:9b-q8_0","digest":"abc123"}]},
    ])
    adapter = QwenOllamaAdapter(opener=lambda request, *, timeout: _Response(next(responses)))
    provenance = adapter.runtime_provenance()
    assert provenance["ollama_version"] == "0.32.15"
    assert provenance["model_digest"] == "abc123"
    assert provenance["model"] == "qwen3.5:9b-q8_0"


def test_default_dry_run_routes_to_v2_without_model_calls():
    completed = subprocess.run(
        ["python", "-m", "inverted.qwen_thinking_tuning", "--dry-run"],
        cwd=Path.cwd(), capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["protocol_version"] == 2
    assert payload["task_families"] == 12
    assert payload["tasks_per_family"] == 600
    assert payload["frozen_atomic_tasks"] == 7200
    assert payload["atomic_batch_size"] == 5
    assert payload["checkpoints"] == [40, 60, 80, 120]


def test_explicit_v1_dry_run_remains_available():
    completed = subprocess.run(
        ["python", "-m", "inverted.qwen_thinking_tuning", "--protocol", "v1", "--dry-run"],
        cwd=Path.cwd(), capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["case_prompts"] == 36
    assert payload["scored_components"] >= 108


def test_powershell_launcher_uses_v2_default_dry_run():
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "scripts/run-qwen-thinking-tuning.ps1", "--dry-run"],
        cwd=Path.cwd(), capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["protocol_version"] == 2


def test_v2_dry_run_reports_honest_call_geometry_and_safe_default_ceiling():
    completed = subprocess.run(
        ["python", "-m", "inverted.qwen_thinking_tuning", "--dry-run"],
        cwd=Path.cwd(), capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    geometry = payload["call_geometry"]
    assert geometry["minimum"] < geometry["expected"] < geometry["worst_case"]
    assert payload["hard_call_ceiling"] >= geometry["worst_case"]
