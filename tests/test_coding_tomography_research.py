from __future__ import annotations

import json
from pathlib import Path

from inverted.assistant_value.coding_tomography_runner import finalize_trial_evidence
from inverted.assistant_value.coding_tomography_research import (
    all_quota_limited_exhausted,
    build_shadow_observer_payload,
    campaign_completion_record,
    capture_instruction_surfaces,
    classify_provider_quota_exhaustion,
    extract_observed_usage,
    model_harness_identity,
    quota_limited_subject_names,
    research_contract,
)


def test_quota_detection_is_terminal_only_for_usage_exhaustion():
    subject = {
        "name": "claude_code",
        "harness": "claude_code",
        "model_backend": "native_claude_subscription",
        "provider_mode": "subscription",
        "quota_limited": True,
    }
    exhausted = classify_provider_quota_exhaustion(
        subject,
        stdout="You've hit your usage limit. Limit resets at 2pm.",
        stderr="",
    )
    transient = classify_provider_quota_exhaustion(
        subject,
        stdout="",
        stderr="HTTP 429 rate_limit_error",
    )
    assert exhausted["status"] == "PROVIDER_QUOTA_EXHAUSTED"
    assert transient["status"] == "AVAILABLE_OR_OTHER_ERROR"


def test_local_routed_subject_is_not_quota_limited():
    subject = {
        "name": "claude_code",
        "harness": "claude_code",
        "model_backend": "gpt-oss:20b",
        "provider_mode": "local_gateway",
        "compute_scope": "local",
        "quota_limited": False,
    }
    row = classify_provider_quota_exhaustion(
        subject,
        stdout="usage limit reached",
        stderr="",
    )
    assert row["status"] == "NOT_QUOTA_LIMITED"
    assert model_harness_identity(subject)["model_backend"] == "gpt-oss:20b"


def test_usage_extraction_retains_records_and_best_effort_totals():
    usage = extract_observed_usage([
        {"type": "result", "usage": {"input_tokens": 10, "output_tokens": 4}},
        {"type": "other", "usage": {"prompt_tokens": 3, "completion_tokens": 2}},
    ])
    assert usage["record_count"] == 2
    assert usage["observed_totals"]["input_tokens"] == 13
    assert usage["observed_totals"]["output_tokens"] == 6
    assert usage["classification"] == "OBSERVED_BEST_EFFORT"


def test_instruction_surface_capture_is_bounded_to_repo_instruction_files(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("verify before stop", encoding="utf-8")
    (tmp_path / "ordinary.py").write_text("secret = 'not-an-instruction'", encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "rules.md").write_text("read migrations", encoding="utf-8")
    capture = capture_instruction_surfaces(tmp_path)
    paths = {row["path"] for row in capture["surfaces"]}
    assert paths == {"CLAUDE.md", ".claude/rules.md"}
    serialized = json.dumps(capture)
    assert "ordinary.py" not in serialized


def test_shadow_observer_payload_never_reads_hidden_oracle(tmp_path: Path):
    (tmp_path / "normalized-native-trajectory.jsonl").write_text(
        json.dumps({"sequence": 1, "event_type": "FILE_READ", "observable_fields": {"path": "app.py"}}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "workspace-diff.json").write_text(json.dumps({"changed_count": 1}), encoding="utf-8")
    (tmp_path / "channel-coverage.json").write_text(json.dumps({"native_normalized_event_count": 1}), encoding="utf-8")
    (tmp_path / "model-visible-instruction-surfaces.json").write_text(json.dumps({"surfaces": []}), encoding="utf-8")
    (tmp_path / "hidden-oracle-results.json").write_text("TOP SECRET EXPECTED ANSWER", encoding="utf-8")
    (tmp_path / "observable-final-response.txt").write_text("done", encoding="utf-8")

    payload = build_shadow_observer_payload(
        trial_root=tmp_path,
        task_prompt="fix the bug",
        subject={"name": "codex"},
    )
    serialized = json.dumps(payload)
    assert "TOP SECRET EXPECTED ANSWER" not in serialized
    assert "hidden-oracle-results.json" in serialized
    assert payload["evidence_class"] == "SYNTHETIC_INFERENCE_INPUT"


def test_provider_completion_contract_preserves_partial_scientific_coverage():
    subjects = [
        {"name": "claude_code", "quota_limited": True},
        {"name": "codex", "quota_limited": True},
        {"name": "local_reference", "quota_limited": False},
    ]
    names = quota_limited_subject_names(subjects)
    assert names == {"claude_code", "codex"}
    status = {"claude_code": "QUOTA_EXHAUSTED", "codex": "QUOTA_EXHAUSTED"}
    assert all_quota_limited_exhausted(status, subjects) is True
    record = campaign_completion_record(
        planned_sessions=160,
        completed_scored_sessions=61,
        provider_status=status,
        remaining_entries=[{"task_id": "remaining"}],
        quota_terminal_trials=2,
        all_quota_exhausted=True,
    )
    assert record["campaign_status"] == "COMPLETE"
    assert record["completion_reason"] == "PROVIDER_USAGE_EXHAUSTED"
    assert record["scientific_coverage"] == "PARTIAL"
    assert record["quota_terminal_is_model_failure"] is False


def test_research_contract_is_additive_and_observer_non_authoritative():
    contract = research_contract({
        "coding_tomography": {
            "shadow_observer": {
                "enabled": True,
                "mode": "post_campaign",
                "model": "gpt-oss:20b",
            }
        }
    })
    assert contract["primary_test_changed"] is False
    assert contract["subject_schedule_changed"] is False
    assert contract["scoring_changed"] is False
    assert contract["shadow_observer"]["authoritative"] is False
    assert contract["shadow_observer"]["may_change_primary_score"] is False


def test_trial_evidence_manifest_refreshes_after_campaign_metadata_change(tmp_path: Path):
    summary = tmp_path / "trial-summary.json"
    summary.write_text('{"phase":"runner"}\n', encoding="utf-8")
    finalize_trial_evidence(tmp_path)
    first = json.loads((tmp_path / "SHA256SUMS.json").read_text(encoding="utf-8"))
    first_hash = next(row["sha256"] for row in first["artifacts"] if row["path"] == "trial-summary.json")

    summary.write_text('{"phase":"campaign"}\n', encoding="utf-8")
    finalize_trial_evidence(tmp_path)
    second = json.loads((tmp_path / "SHA256SUMS.json").read_text(encoding="utf-8"))
    second_hash = next(row["sha256"] for row in second["artifacts"] if row["path"] == "trial-summary.json")

    assert first_hash != second_hash


def test_real_provider_quota_wording_is_recognized():
    claude = classify_provider_quota_exhaustion(
        {"name": "claude_code", "quota_limited": True},
        stdout="You've hit your session limit · resets 1:30pm",
        stderr="",
    )
    codex = classify_provider_quota_exhaustion(
        {"name": "codex", "quota_limited": True},
        stdout="",
        stderr="HTTP 429 - usage_limit_reached\nplan_type: plus",
    )
    assert claude["status"] == "PROVIDER_QUOTA_EXHAUSTED"
    assert codex["status"] == "PROVIDER_QUOTA_EXHAUSTED"
