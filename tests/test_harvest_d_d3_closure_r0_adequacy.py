from __future__ import annotations

from dataclasses import replace

from inverted.harvest_d.d3_closure_adequacy import ClaimAdequacyInputs, evaluate_claim_adequacy


def _base() -> ClaimAdequacyInputs:
    return ClaimAdequacyInputs(
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


def test_missing_r0_required_artifact_fails_physical_authorization_closed():
    inputs = replace(_base(), r0_required_artifacts_complete=False)
    report = evaluate_claim_adequacy(inputs)

    assert report.physical_execution_authorized is False
    assert any("r0" in blocker.lower() and "artifact" in blocker.lower() for blocker in report.blockers)


def test_historical_prior_counted_as_fresh_fails_evidence_tier_integrity_gate():
    inputs = replace(_base(), evidence_tier_integrity=False)
    report = evaluate_claim_adequacy(inputs)

    assert report.physical_execution_authorized is False
    assert any("evidence tier" in blocker.lower() for blocker in report.blockers)


def test_uncovered_mandatory_model_free_obligation_fails_closed():
    inputs = replace(_base(), uncovered_mandatory_obligations=1)
    report = evaluate_claim_adequacy(inputs)

    assert report.physical_execution_authorized is False
    assert any("mandatory" in blocker.lower() and "obligation" in blocker.lower() for blocker in report.blockers)


def test_complete_r0_integrity_fields_do_not_create_a_new_blocker_by_themselves():
    inputs = replace(
        _base(),
        r0_required_artifacts_complete=True,
        evidence_tier_integrity=True,
        uncovered_mandatory_obligations=0,
    )
    report = evaluate_claim_adequacy(inputs)

    assert report.physical_execution_authorized is True
    assert report.blockers == ()
