from inverted.harvest_d.d3_assistance import (
    ASSISTANCE_MECHANISMS,
    DispositionCompiler,
    SystemSemantics,
    assistance_opportunity,
    evaluate_assistance,
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


def test_admissible_action_restriction_has_target_off_and_sham_conditions():
    context = {"candidate_actions": ["read", "write", "delete"], "admissible_actions": ["read"]}
    target = evaluate_assistance("A2", "TARGET", context)
    off = evaluate_assistance("A2", "OFF", context)
    sham = evaluate_assistance("A2", "SHAM", context)
    assert target.output["candidate_actions"] == ["read"]
    assert off.output["candidate_actions"] == ["read", "write", "delete"]
    assert sham.mode == "SHAM"
    assert target.mechanism_id == off.mechanism_id == sham.mechanism_id == "A2"


def test_opportunity_records_non_events_not_only_triggered_interventions():
    eligible = assistance_opportunity("A3", eligible=True, triggered=False, reason="evidence already sufficient")
    ineligible = assistance_opportunity("A7", eligible=False, triggered=False, reason="no authority boundary")
    assert eligible.status == "ELIGIBLE_NOT_TRIGGERED"
    assert ineligible.status == "INELIGIBLE"
    assert eligible.reason and ineligible.reason
