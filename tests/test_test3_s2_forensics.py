import json
from datetime import datetime, timezone

from inverted.models import CompletionResult, MockModelAdapter
from inverted.oracle import evaluate_task
from inverted.telemetry import ModelCallRecord
from inverted.test2_local import BoundedModelCaller
from inverted.test2_types import PhysicalCallBudget
from inverted.test3_s2_cases import build_holdout_b, build_seed_failure_s2
from inverted.test3_s2_forensics import S2ForensicJournal
from inverted.test3_s2_runtime import decode_s2_candidate_response, decode_s2_repair_response


class _RawAdapter:
    provider = "raw-test"
    model = "raw-test-model"
    max_retries = 0

    def complete(self, messages, *, role, context):
        raw = {
            "model": self.model,
            "created_at": "2026-09-01T00:00:00Z",
            "message": {"role": "assistant", "content": '{"actions":[]}', "thinking": "private-test-thinking"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 7,
            "eval_count": 3,
            "custom_provider_field": {"nested": [1, 2, 3]},
        }
        now = datetime.now(timezone.utc).isoformat()
        record = ModelCallRecord(
            call_id=str(context.get("call_id") or "call"),
            run_id=str(context.get("run_id") or "run"),
            trial_id=str(context.get("trial_id") or "trial"),
            candidate_id=context.get("candidate_id"),
            role=role,
            model=self.model,
            provider=self.provider,
            start_ts=now,
            end_ts=now,
            latency_s=0.001,
            status_code=200,
            finish_reason="stop",
            prompt=messages,
            response=raw["message"]["content"],
        )
        return CompletionResult(raw["message"]["content"], record, raw)


def test_s2_forensic_journal_flushes_each_record_and_verifies_hash_chain(tmp_path):
    journal = S2ForensicJournal(tmp_path, "forensic-test")
    first = journal.append("run_initialized", {"value": 1}, trial_id="trial-a")
    path = tmp_path / "forensic_journal.jsonl"
    assert path.is_file()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0] == first
    assert rows[0]["sequence"] == 1
    assert rows[0]["previous_sha256"] is None
    assert rows[0]["record_sha256"]

    second = journal.append("router_decision", {"action": "retry_qwen"}, call_id="call-2")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    assert rows[1] == second
    assert rows[1]["sequence"] == 2
    assert rows[1]["previous_sha256"] == rows[0]["record_sha256"]
    integrity = journal.snapshot_integrity()
    assert integrity["valid"] is True
    assert integrity["record_count"] == 2
    assert integrity["last_record_sha256"] == rows[-1]["record_sha256"]

    rows[0]["payload"]["value"] = 99
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    tampered = journal.snapshot_integrity()
    assert tampered["valid"] is False
    assert tampered["first_invalid_sequence"] == 1


def test_bounded_completion_retains_complete_raw_provider_payload():
    caller = BoundedModelCaller(PhysicalCallBudget(max_calls=1))
    completion = caller.complete(
        _RawAdapter(),
        [{"role": "user", "content": "test"}],
        role="executor",
        context={"run_id": "raw-run", "trial_id": "raw-trial", "call_id": "raw-call"},
        allow_cache=False,
    )
    assert completion.raw["custom_provider_field"] == {"nested": [1, 2, 3]}
    assert completion.raw["message"]["thinking"] == "private-test-thinking"
    assert completion.raw["prompt_eval_count"] == 7


def test_s2_candidate_decode_preserves_exact_parse_decode_and_application_failure_stages():
    task = build_holdout_b()[0].task

    candidate, diagnostic = decode_s2_candidate_response(task, "{", "parse-failure")
    assert candidate is None
    assert diagnostic["failure_stage"] == "response_json_parse_failure"
    assert diagnostic["error_class"] == "JSONDecodeError"

    candidate, diagnostic = decode_s2_candidate_response(task, '{"actions":[{"op":"set"}]}', "decode-failure")
    assert candidate is None
    assert diagnostic["failure_stage"] == "response_schema_or_action_decode_failure"
    assert diagnostic["error_class"] in {"KeyError", "TypeError", "ValueError"}

    candidate, diagnostic = decode_s2_candidate_response(
        task,
        '{"actions":[{"op":"definitely_invalid","path":"invalid.path","value":1}]}',
        "application-failure",
    )
    assert candidate is None
    assert diagnostic["failure_stage"] == "action_application_failure"
    assert diagnostic["error_class"]


def test_s2_repair_decode_distinguishes_patch_parse_from_composition_failure():
    case = build_holdout_b()[0]
    seed = build_seed_failure_s2(case)
    result = evaluate_task(case.task, seed.state, seed.actions)
    failed = list(result.failed_requirement_ids)

    candidate, diagnostic = decode_s2_repair_response(case.task, seed, "{", failed, "repair-parse")
    assert candidate is None
    assert diagnostic["failure_stage"] == "repair_patch_parse_failure"
    assert diagnostic["error_class"] == "JSONDecodeError"

    candidate, diagnostic = decode_s2_repair_response(
        case.task,
        seed,
        '{"actions":[{"op":"definitely_invalid","path":"invalid.path","value":1}]}',
        failed,
        "repair-compose",
    )
    assert candidate is None
    assert diagnostic["failure_stage"] == "repair_patch_composition_failure"
    assert diagnostic["error_class"]
