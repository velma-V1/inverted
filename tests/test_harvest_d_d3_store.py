from dataclasses import replace
import json

import pytest

from inverted.harvest_d.d3_store import D3EvidenceStore, D3IntegrityError
from inverted.harvest_d.d3_types import D3Event, EvidenceAdmissibility


def make_event(event_id="e1", sequence=1):
    return replace(
        D3Event.for_test(model_visible={"state": 1}, system_known={"state": 1}),
        event_id=event_id,
        sequence=sequence,
    )


def complete_bundle(call_id="call-1"):
    return {
        "physical_model_call_id": call_id,
        "raw_request": {"messages": [{"role": "user", "content": "x"}]},
        "raw_response": {"payload": {"message": {"content": "ok"}}},
        "normalized_call": {"physical_model_call_id": call_id, "semantic_success": True},
        "information_packet": {"packet_id": "p1"},
        "score_raw": {"physical_model_call_id": call_id, "score": 1},
        "score_normalized": {"physical_model_call_id": call_id, "semantic_success": True},
        "runtime_telemetry": {"physical_model_call_id": call_id, "latency_ms": 1.0},
        "scheduler_event": {"decision_id": "s1", "physical_model_call_id": call_id},
    }


def test_store_never_overwrites_raw_event_identity(tmp_path):
    store = D3EvidenceStore(tmp_path)
    store.append_event(make_event())
    with pytest.raises(D3IntegrityError):
        store.append_event(make_event(sequence=2))


def test_call_is_not_admissible_until_required_capture_commits(tmp_path):
    store = D3EvidenceStore(tmp_path)
    bundle = complete_bundle()
    bundle.pop("raw_response")
    status = store.append_call_bundle(bundle)
    assert status.admissibility is EvidenceAdmissibility.DIAGNOSTIC_ONLY
    assert "raw_response" in status.missing_required


def test_complete_call_bundle_is_promotion_admissible(tmp_path):
    store = D3EvidenceStore(tmp_path)
    status = store.append_call_bundle(complete_bundle())
    assert status.admissibility is EvidenceAdmissibility.ADMISSIBLE
    assert store.capture_status("call-1").admissibility is EvidenceAdmissibility.ADMISSIBLE


def test_integrity_verification_detects_manual_mutation(tmp_path):
    store = D3EvidenceStore(tmp_path)
    store.append_event(make_event())
    store.append_call_bundle(complete_bundle())
    store.commit_checkpoint()
    (tmp_path / "d3_system_events.jsonl").write_text("corrupt\n", encoding="utf-8")
    with pytest.raises(D3IntegrityError):
        store.verify_integrity()


def test_store_creates_required_queryable_record_families(tmp_path):
    D3EvidenceStore(tmp_path)
    expected = {
        "d3_system_events.jsonl",
        "d3_call_ledger.jsonl",
        "d3_raw_model_requests.jsonl",
        "d3_raw_model_responses.jsonl",
        "d3_normalized_model_calls.jsonl",
        "d3_information_packets.jsonl",
        "d3_scheduler_events.jsonl",
        "d3_capture_field_matrix.jsonl",
        "d3_intervention_opportunities.jsonl",
        "d3_decision_opportunity_sets.jsonl",
        "d3_case_structural_features.jsonl",
        "d3_model_behavior_features.jsonl",
        "d3_decision_boundary_telemetry.jsonl",
        "d3_causal_claim_graph.jsonl",
        "d3_claim_evidence_edges.jsonl",
        "d3_protocol_violations.jsonl",
        "d3_assumption_ledger.jsonl",
    }
    assert expected <= {p.name for p in tmp_path.iterdir()}


def test_unknown_safe_fields_are_preserved_in_extras(tmp_path):
    store = D3EvidenceStore(tmp_path)
    bundle = complete_bundle()
    bundle["normalized_call"]["future_runtime_field"] = 7
    store.append_call_bundle(bundle)
    row = json.loads((tmp_path / "d3_normalized_model_calls.jsonl").read_text().splitlines()[0])
    assert row["future_runtime_field"] == 7
