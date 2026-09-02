import csv
import copy
import json

import httpx
import pytest

from inverted.models import MockModelAdapter
from inverted.test2_provenance import collect_ollama_provenance
from inverted.test3_s2_artifacts import REQUIRED_S2_FILES, Test3S2ArtifactWriter
from inverted.test3_s2_cases import build_holdout_b
from inverted.test3_s2_cli import main
from inverted.test3_s2_forensics import S2ForensicJournal
from inverted.test3_s2_observability import router_observability_analysis
from inverted.test3_s2_runtime import run_s2_screen


def _models():
    return {
        "qwen3.5:9b-q8_0": MockModelAdapter("qwen3.5:9b-q8_0"),
        "cogito:3b-v1-preview-llama-q8_0": MockModelAdapter("cogito:3b-v1-preview-llama-q8_0"),
        "llama3.1:8b": MockModelAdapter("llama3.1:8b"),
    }


def test_s2_midrun_abort_preserves_raw_completed_call_prefix_on_disk(tmp_path):
    journal = S2ForensicJournal(tmp_path, "abort-prefix")

    def inject(point, payload):
        if point == "after_model_completion_before_processing" and int(payload["physical_call_number"]) == 3:
            raise RuntimeError("intentional-midrun-abort")

    with pytest.raises(RuntimeError, match="intentional-midrun-abort") as caught:
        run_s2_screen(
            cases=build_holdout_b(),
            model_by_name=_models(),
            run_id="abort-prefix",
            journal=journal,
            failure_injector=inject,
        )

    records = journal.read_records()
    completed = [row for row in records if row.get("event_type") == "model_call_completed"]
    assert len(completed) == 3
    assert all(row["payload"].get("raw_provider_response") == {"mock": True} for row in completed)
    assert records[-1]["event_type"] == "runtime_aborted"
    partial = caught.value.s2_partial_runtime
    assert partial["runtime_complete"] is False
    assert partial["physical_model_calls"] == 3
    assert partial["action_budget"]["combined_used"] == 3
    assert len(partial["model_calls"]) == 2
    assert partial["journal_integrity"]["valid"] is True


def test_s2_abort_after_router_decision_retains_decision_before_any_model_call(tmp_path):
    journal = S2ForensicJournal(tmp_path, "decision-abort")

    def inject(point, payload):
        if point == "after_router_decision":
            raise RuntimeError("abort-after-decision")

    with pytest.raises(RuntimeError, match="abort-after-decision"):
        run_s2_screen(
            cases=build_holdout_b(),
            model_by_name=_models(),
            run_id="decision-abort",
            journal=journal,
            failure_injector=inject,
        )

    records = journal.read_records()
    decisions = [row for row in records if row.get("event_type") == "router_decision"]
    calls = [row for row in records if row.get("event_type") == "model_call_completed"]
    assert len(decisions) == 1
    assert calls == []
    assert records[-1]["event_type"] == "runtime_aborted"


def test_ollama_provenance_retains_complete_raw_payloads_without_extra_endpoints():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "9.9.9", "extra_version_field": {"x": 1}})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "model-a", "digest": "abc", "size": 7, "details": {"q": 8}}], "extra_tags": [1, 2]})
        if path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": "model-a", "size_vram": 123}], "extra_ps": True})
        if path == "/api/show":
            return httpx.Response(200, json={"details": {"family": "qwen"}, "model_info": {"layers": 99}, "template": "tmpl", "system": "sys", "capabilities": ["completion"], "parameters": "p", "unknown_show_field": {"keep": "me"}})
        raise AssertionError(path)

    result = collect_ollama_provenance(
        "http://ollama.test",
        ("model-a",),
        transport=httpx.MockTransport(handler),
    )
    raw = result["raw_payloads"]
    assert raw["version"]["extra_version_field"] == {"x": 1}
    assert raw["tags"]["extra_tags"] == [1, 2]
    assert raw["ps"]["extra_ps"] is True
    assert raw["show"]["model-a"]["unknown_show_field"] == {"keep": "me"}
    assert result["zero_inference_endpoints"] == ["/api/version", "/api/tags", "/api/show", "/api/ps"]


def test_router_observability_analysis_detects_b2_alias_and_b3_resolution_without_mutation():
    same_b2 = {
        "failed_requirement_ids": ["r1"],
        "failed_requirement_kinds": ["equal"],
        "failed_count": 1,
        "failure_signature": "equal:x",
        "deterministic_success": False,
        "catastrophic": False,
    }
    runtime = {
        "holdout_manifest": [
            {"task_id": "t1", "perturbation_class": "localized", "fixture_injected_faults": ["fault-a"]},
            {"task_id": "t2", "perturbation_class": "structural", "fixture_injected_faults": ["fault-b"]},
        ],
        "routing_state_snapshots": [
            {"arm_id": "S2-B2", "task_id": "t1", "step_index": 0, "router_view": same_b2},
            {"arm_id": "S2-B2", "task_id": "t2", "step_index": 0, "router_view": same_b2},
            {"arm_id": "S2-B3", "task_id": "t1", "step_index": 0, "router_view": {**same_b2, "family": "state", "complexity": 1, "previous_action": None, "previous_model": None, "retry_count": 0, "budget_spent": 0, "budget_remaining": 732}},
            {"arm_id": "S2-B3", "task_id": "t2", "step_index": 0, "router_view": {**same_b2, "family": "dependency", "complexity": 2, "previous_action": None, "previous_model": None, "retry_count": 0, "budget_spent": 0, "budget_remaining": 732}},
        ],
        "routing_decisions": [
            {"arm_id": "S2-B2", "task_id": "t1", "step_index": 0, "action_selected": "retry_qwen"},
            {"arm_id": "S2-B2", "task_id": "t2", "step_index": 0, "action_selected": "retry_qwen"},
            {"arm_id": "S2-B3", "task_id": "t1", "step_index": 0, "action_selected": "repair_cogito"},
            {"arm_id": "S2-B3", "task_id": "t2", "step_index": 0, "action_selected": "switch_llama"},
        ],
        "trials": [
            {"arm_id": "S2-B2", "task_id": "t1", "success": True, "catastrophic": False},
            {"arm_id": "S2-B2", "task_id": "t2", "success": False, "catastrophic": False},
            {"arm_id": "S2-B3", "task_id": "t1", "success": True, "catastrophic": False},
            {"arm_id": "S2-B3", "task_id": "t2", "success": True, "catastrophic": False},
        ],
    }
    before = copy.deepcopy(runtime)
    result = router_observability_analysis(runtime)
    assert runtime == before
    summary = result["summary"]
    assert summary["collision_count"] == 1
    assert summary["ambiguous_case_count"] == 2
    assert summary["largest_collision_group_size"] == 2
    assert summary["b2_to_b3_collisions_resolved"] == 1
    assert summary["b3_collisions_remaining"] == 0
    b2_collision = [row for row in result["rows"] if row["arm_id"] == "S2-B2" and row["collision"]]
    assert len(b2_collision) == 1
    assert set(b2_collision[0]["hidden_perturbation_classes"]) == {"localized", "structural"}
    assert b2_collision[0]["distinct_hidden_fault_truths"] == 2


def test_partial_s2_artifact_packet_cannot_claim_protocol_or_architecture_validity(tmp_path):
    evidence = {
        "run_id": "partial-run",
        "protocol_revision": "S2-R1",
        "holdout": "B-R1",
        "physical_model_calls": 3,
        "action_budget": {"limit": 732, "combined_used": 3, "remaining": 729, "by_kind": {"model_call": 3}},
        "trials": [],
        "model_calls": [],
        "routing_decisions": [],
        "routing_state_snapshots": [],
        "validator_results": [],
        "events": [],
        "holdout_manifest": [],
        "external_action_ledger": [],
        "raw_model_transactions": [],
        "parse_and_composition_failures": [],
        "router_observability_collisions": [],
        "router_observability_summary": {},
        "journal_integrity": {"valid": True, "record_count": 1},
        "environment_provenance": {"python": "test"},
        "abort_state": {"error_class": "RuntimeError", "error": "boom"},
        "verdict": {"verdict": "SHOULD_NOT_SURVIVE", "protocol_valid_for_primary_claim": True, "tier_a_architecture_claim": True},
    }
    written = Test3S2ArtifactWriter(tmp_path).write_all(evidence, partial=True)
    assert set(REQUIRED_S2_FILES).issubset(written)
    master = json.loads((tmp_path / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert master["evidence_status"] == "PARTIAL_ABORTED"
    assert master["protocol_valid_for_primary_claim"] is False
    assert master["architecture_claims_authorized"] is False
    assert verdict["protocol_valid_for_primary_claim"] is False
    assert verdict["tier_a_architecture_claim"] is False
    complete = (tmp_path / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    assert "PARTIAL/ABORTED EVIDENCE" in complete


def test_real_cli_preflight_failure_writes_abort_packet_and_action_ledger(tmp_path, monkeypatch):
    import inverted.test3_s2_cli as cli

    def fail_preflight(base_url, model_names, action_budget, **kwargs):
        action_budget.reserve("provenance_api_call")
        raise RuntimeError("intentional-provenance-failure")

    monkeypatch.setattr(cli, "_provenance_snapshot", fail_preflight)
    output = tmp_path / "preflight-failure"
    code = main([
        "run",
        "--config", "configs/test3-s2.yaml",
        "--output-dir", str(output),
        "--run-id", "preflight-failure",
        "--authorize-tier-a",
    ])
    assert code == 1
    assert (output / "forensic_journal.jsonl").is_file()
    abort = json.loads((output / "abort_state.json").read_text(encoding="utf-8"))
    assert abort["stage"] == "pre_run_provenance"
    assert abort["error_class"] == "RuntimeError"
    with (output / "external_action_ledger.jsonl").open(encoding="utf-8") as handle:
        ledger = [json.loads(line) for line in handle if line.strip()]
    assert ledger
    assert ledger[-1]["kind"] == "provenance_api_call"
    verdict = json.loads((output / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["protocol_valid_for_primary_claim"] is False
    assert verdict["tier_a_architecture_claim"] is False


def test_real_cli_postrun_provenance_failure_preserves_720_calls_and_withholds_claims(tmp_path, monkeypatch):
    import inverted.test3_s2_cli as cli

    snapshot_count = 0

    def fake_snapshot(base_url, model_names, action_budget, **kwargs):
        nonlocal snapshot_count
        ledger = kwargs.get("ledger")
        journal = kwargs.get("journal")
        stage = kwargs.get("stage")
        snapshot_count += 1
        if snapshot_count == 1:
            for index in range(6):
                action_budget.reserve("provenance_api_call")
                row = {
                    "kind": "provenance_api_call",
                    "stage": stage,
                    "ordinal": index + 1,
                    "budget_after_reservation": action_budget.snapshot(),
                }
                if ledger is not None:
                    ledger.append(row)
                if journal is not None:
                    journal.append("external_action_reserved", row)
            return {
                "server_version": "test",
                "models": {name: {"requested_name": name, "tag_digest": f"digest-{name}"} for name in model_names},
                "raw_payloads": {"version": {"version": "test"}, "tags": {}, "ps": {}, "show": {}},
            }
        action_budget.reserve("provenance_api_call")
        raise RuntimeError("intentional-postrun-provenance-failure")

    monkeypatch.setattr(cli, "_provenance_snapshot", fake_snapshot)
    monkeypatch.setattr(cli, "_adapter", lambda name, settings: MockModelAdapter(name))
    output = tmp_path / "postrun-failure"
    code = main([
        "run",
        "--config", "configs/test3-s2.yaml",
        "--output-dir", str(output),
        "--run-id", "postrun-failure",
        "--authorize-tier-a",
    ])
    assert code == 0
    master = json.loads((output / "00-MASTER-INDEX.json").read_text(encoding="utf-8"))
    verdict = json.loads((output / "verdict.json").read_text(encoding="utf-8"))
    assert master["evidence_status"] == "COMPLETE"
    assert master["physical_model_calls"] == 720
    assert master["combined_external_actions"] == 727
    assert verdict["verdict"] == "S2_INSTRUMENTATION_WARNING"
    assert verdict["protocol_valid_for_primary_claim"] is False
    assert verdict["tier_a_architecture_claim"] is False
    assert json.loads((output / "abort_state.json").read_text(encoding="utf-8")) == {}
    with (output / "raw_model_transactions.jsonl").open(encoding="utf-8") as handle:
        transactions = [json.loads(line) for line in handle if line.strip()]
    assert len(transactions) == 720
    with (output / "external_action_ledger.jsonl").open(encoding="utf-8") as handle:
        ledger = [json.loads(line) for line in handle if line.strip()]
    assert sum(row.get("kind") == "provenance_api_call" for row in ledger) == 7
    assert sum(row.get("kind") == "model_call" for row in ledger) == 720
