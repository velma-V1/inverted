import pytest

from inverted.harvest_d.d3_closure_recovery import (
    RecoveryOutcome,
    classify_recovery_outcome,
    validate_recovery_trajectory,
)


def _trajectory(**overrides):
    row = {
        "initial_state": {"version": 1},
        "first_divergence": "STALE_PLAN",
        "first_detection": "GUARD",
        "failure_class": "STATE",
        "available_recovery_frontier": ["REPLAN", "RETRY"],
        "selected_recovery": "REPLAN",
        "system_admission": "ALLOW",
        "resulting_state": {"version": 2},
        "verifier_postcondition": "PASS",
        "external_effect_status": "NOT_COMMITTED",
        "final_status": "RECOVERED",
    }
    row.update(overrides)
    return row


def test_recovery_trajectory_requires_all_causal_stages():
    row = _trajectory()
    row.pop("first_detection")
    with pytest.raises(ValueError):
        validate_recovery_trajectory(row)


def test_unknown_external_effect_forbids_blind_retry():
    with pytest.raises(ValueError):
        validate_recovery_trajectory(
            _trajectory(external_effect_status="UNKNOWN", selected_recovery="RETRY")
        )


def test_recovery_outcome_distinguishes_migration_and_success():
    assert classify_recovery_outcome(_trajectory()) is RecoveryOutcome.RECOVERED
    assert classify_recovery_outcome(
        _trajectory(final_status="MIGRATED", verifier_postcondition="FAIL")
    ) is RecoveryOutcome.MIGRATED
