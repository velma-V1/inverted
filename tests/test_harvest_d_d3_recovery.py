from inverted.harvest_d.d3_recovery import (
    RecoveryPolicy,
    classify_recovery_trajectory,
    failure_migrated,
    simulate_recovery,
    trajectory,
)
from inverted.harvest_d.d3_types import RecoveryChoice, RecoveryStage


def test_recovery_records_detection_diagnosis_selection_execution_verification_separately():
    trace = simulate_recovery(fault="STALE_STATE")
    stages = [step.stage for step in trace.steps]
    assert stages == [
        RecoveryStage.DETECTION,
        RecoveryStage.DIAGNOSIS,
        RecoveryStage.SELECTION,
        RecoveryStage.ADMISSION,
        RecoveryStage.EXECUTION,
        RecoveryStage.VERIFICATION,
    ]
    assert trace.stage(RecoveryStage.SELECTION).choice is RecoveryChoice.REPLAN
    assert trace.stage(RecoveryStage.VERIFICATION).outcome == "RECOVERED"


def test_unknown_external_effect_requires_reconciliation_before_retry():
    decision = RecoveryPolicy().decide(external_effect_status="UNKNOWN")
    assert decision.choice is RecoveryChoice.RECONCILE
    assert decision.allow_retry is False


def test_missing_evidence_routes_to_acquire_evidence_not_retry():
    decision = RecoveryPolicy().decide(missing_required_evidence=True)
    assert decision.choice is RecoveryChoice.ACQUIRE_EVIDENCE
    assert decision.allow_retry is False


def test_local_fix_that_breaks_global_invariant_is_failure_migration():
    trace = trajectory(local_recovered=True, global_invariant_ok=False)
    assert failure_migrated(trace) is True
    assert classify_recovery_trajectory(trace) == "MIGRATED"


def test_clean_recovery_is_not_migration():
    trace = trajectory(local_recovered=True, global_invariant_ok=True)
    assert failure_migrated(trace) is False
    assert classify_recovery_trajectory(trace) == "RECOVERED"
