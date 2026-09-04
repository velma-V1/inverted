from inverted.harvest_d.d3_closure_assistance import (
    AssistanceMode,
    apply_predecision_assistance,
    evaluate_system_assistance,
)
from inverted.harvest_d.types import Disposition


def _context():
    return {
        "canonical_state": {"version": 7},
        "candidate_actions": ["USE_CURRENT", "USE_STALE"],
        "admissible_actions": ["USE_CURRENT"],
        "required_evidence": ["receipt"],
        "available_evidence": [],
        "missing_evidence": ["receipt"],
        "dependencies": {"order": "STATE_BEFORE_ACTION"},
        "postcondition_met": False,
        "hard_invariant_ok": True,
        "external_effect_status": "NOT_COMMITTED",
        "authority_allows": True,
        "irreversible": False,
        "risk": "MEDIUM",
    }


def test_predecision_target_is_visible_before_inference_but_off_and_sham_are_not():
    target = apply_predecision_assistance("A1", AssistanceMode.TARGET, _context())
    off = apply_predecision_assistance("A1", AssistanceMode.OFF, _context())
    sham = apply_predecision_assistance("A1", AssistanceMode.SHAM, _context())
    assert "canonical_state" in target.model_visible_additions
    assert off.model_visible_additions == {}
    assert sham.model_visible_additions != target.model_visible_additions
    assert sham.target_semantics_injected is False


def test_a2_restricts_model_visible_action_frontier():
    target = apply_predecision_assistance("A2", AssistanceMode.TARGET, _context())
    assert target.model_visible_additions["admissible_actions"] == ["USE_CURRENT"]


def test_system_assistance_is_scored_by_decision_semantics():
    outcome = evaluate_system_assistance(
        "A6",
        proposal={"answer": "USE_CURRENT"},
        context=_context(),
        expected_disposition=Disposition.ACQUIRE_EVIDENCE,
    )
    assert outcome.actual_disposition is Disposition.ACQUIRE_EVIDENCE
    assert outcome.correct is True
    assert outcome.reason
