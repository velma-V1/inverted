from inverted.harvest_d.d3_assistance import (
    ASSISTANCE_MECHANISMS,
    DispositionCompiler,
    SystemSemantics,
    assistance_opportunity,
    evaluate_assistance,
    replay_assistance_suite,
)
from inverted.harvest_d.types import Disposition


def test_all_normative_assistance_mechanisms_are_addressable():
    assert tuple(ASSISTANCE_MECHANISMS) == tuple(f"A{i}" for i in range(1, 12))


def test_disposition_compiler_uses_system_semantics_not_case_ids():
    result = DispositionCompiler().compile(SystemSemantics(missing_required_evidence=True))
    assert result.disposition is Disposition.ACQUIRE_EVIDENCE
    assert "case_id" not in result.inputs_used


def test_unknown_external_effect_never_compiles_to_retry():
    result = DispositionCompiler().compile(SystemSemantics(external_effect_status="UNKNOWN"))
    assert result.recovery in {"RECONCILE", "ESCALATE", "SAFE_STOP"}
    assert result.recovery != "RETRY"


def test_hard_invariant_failure_compiles_to_safe_stop():
    result = DispositionCompiler().compile(SystemSemantics(hard_invariant_ok=False))
    assert result.disposition is Disposition.SAFE_STOP


def _rich_context():
    return {
        "canonical_state": {"resource": "r1", "version": 3},
        "model_state_claim": {"resource": "r1", "version": 2},
        "candidate_actions": ["read", "write", "delete"],
        "admissible_actions": ["read"],
        "required_evidence": ["receipt", "state_hash"],
        "available_evidence": ["state_hash"],
        "missing_evidence": ["receipt"],
        "dependencies": {"order": ["parent", "child"]},
        "postcondition_met": False,
        "missing_required_evidence": True,
        "external_effect_status": "UNKNOWN",
        "hard_invariant_ok": True,
        "authority_allows": False,
        "authority_scope": ["r1"],
        "requested_resource": "r2",
        "irreversible": True,
        "risk": "HIGH",
        "failure_signature": "STALE_PLAN",
        "recovery_state": "RECONCILE",
        "novelty": "HIGH",
        "boundary_exceeded": True,
        "model_disposition": "EXECUTE",
        "model_answer": "delete",
    }


def test_every_assistance_mechanism_has_target_off_and_matched_sham_behavior():
    context = _rich_context()
    for mechanism_id in ASSISTANCE_MECHANISMS:
        target = evaluate_assistance(mechanism_id, "TARGET", context)
        off = evaluate_assistance(mechanism_id, "OFF", context)
        sham = evaluate_assistance(mechanism_id, "SHAM", context)
        assert target.mechanism_id == off.mechanism_id == sham.mechanism_id == mechanism_id
        assert target.mode == "TARGET"
        assert off.mode == "OFF"
        assert sham.mode == "SHAM"
        assert off.output == context
        assert sham.output == context
        assert target.output != context, mechanism_id
        assert target.reason


def test_admissible_action_restriction_has_target_off_and_sham_conditions():
    context = {"candidate_actions": ["read", "write", "delete"], "admissible_actions": ["read"]}
    target = evaluate_assistance("A2", "TARGET", context)
    off = evaluate_assistance("A2", "OFF", context)
    sham = evaluate_assistance("A2", "SHAM", context)
    assert target.output["candidate_actions"] == ["read"]
    assert off.output["candidate_actions"] == ["read", "write", "delete"]
    assert sham.mode == "SHAM"
    assert target.mechanism_id == off.mechanism_id == sham.mechanism_id == "A2"


def test_replay_suite_produces_33_zero_call_counterfactuals_from_one_source_call():
    rows = replay_assistance_suite(
        source_physical_model_call_id="d3-call-1",
        context=_rich_context(),
    )
    assert len(rows) == 33
    assert {row["source_physical_model_call_id"] for row in rows} == {"d3-call-1"}
    assert {row["mode"] for row in rows} == {"OFF", "TARGET", "SHAM"}
    assert {row["mechanism_id"] for row in rows} == set(ASSISTANCE_MECHANISMS)
    assert all(row["physical_model_calls_used"] == 0 for row in rows)


def test_opportunity_records_non_events_not_only_triggered_interventions():
    eligible = assistance_opportunity("A3", eligible=True, triggered=False, reason="evidence already sufficient")
    ineligible = assistance_opportunity("A7", eligible=False, triggered=False, reason="no authority boundary")
    assert eligible.status == "ELIGIBLE_NOT_TRIGGERED"
    assert ineligible.status == "INELIGIBLE"
    assert eligible.reason and ineligible.reason
