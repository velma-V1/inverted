from __future__ import annotations

from inverted.harvest_d.d3_closure_adequacy import (
    ClaimAdequacyInputs,
    evaluate_claim_adequacy,
)


def _complete_inputs(**changes):
    values = dict(
        claim_space_manifest_present=True,
        search_space_manifest_present=True,
        pairwise_coverage_ratio=1.0,
        required_three_way_coverage_ratio=1.0,
        cost_calibration_complete=True,
        reproducibility_calibration_complete=True,
        cost_scaled_scheduler_ready=True,
        protected_discovery_ready=True,
        local_minimality_ready=True,
        real_recovery_ready=True,
        sealed_confirmation_protected=True,
        blocker_audit_green=True,
        launcher_path_green=True,
        unresolved_hard_blockers=0,
        unresolved_scientific_risks=0,
    )
    values.update(changes)
    return ClaimAdequacyInputs(**values)


def test_physical_execution_is_authorized_only_when_every_mandatory_adequacy_gate_is_green():
    report = evaluate_claim_adequacy(_complete_inputs())
    assert report.physical_execution_authorized is True
    assert report.claim_ceiling == "OPTIMIZATION_ELIGIBLE"


def test_missing_pairwise_coverage_blocks_physical_execution_and_broad_optimality_claim():
    report = evaluate_claim_adequacy(_complete_inputs(pairwise_coverage_ratio=0.91))
    assert report.physical_execution_authorized is False
    assert report.claim_ceiling in {"SCREEN", "BEST_OF_TESTED"}
    assert "pairwise" in " ".join(report.blockers).lower()


def test_missing_minimality_engine_prevents_minimum_sufficient_claim_even_if_other_gates_are_green():
    report = evaluate_claim_adequacy(_complete_inputs(local_minimality_ready=False))
    assert report.physical_execution_authorized is False
    assert report.minimum_sufficient_claim_eligible is False


def test_synthetic_recovery_is_not_enough_to_authorize_recovery_claims():
    report = evaluate_claim_adequacy(_complete_inputs(real_recovery_ready=False))
    assert report.physical_execution_authorized is False
    assert report.recovery_claim_eligible is False


def test_any_hard_blocker_or_unbounded_scientific_risk_fails_closed():
    hard = evaluate_claim_adequacy(_complete_inputs(unresolved_hard_blockers=1))
    risk = evaluate_claim_adequacy(_complete_inputs(unresolved_scientific_risks=1))
    assert hard.physical_execution_authorized is False
    assert risk.physical_execution_authorized is False
