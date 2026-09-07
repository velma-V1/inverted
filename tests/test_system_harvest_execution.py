from inverted.system_harvest.execution import AttemptOutcome, advance_example


def test_wrong_or_stalled_model_requires_snapshot_and_escalation():
    failed = advance_example("C", "S", "E", 0, AttemptOutcome.INCORRECT)
    assert failed.action == "CAPTURE_AND_ESCALATE"
    assert failed.snapshot_required is True
    assert failed.next_escalation_level == 1
    assert failed.terminal_status is None

    stalled = advance_example("C", "S", "E", 2, AttemptOutcome.STALL)
    assert stalled.action == "CAPTURE_AND_ESCALATE"
    assert stalled.next_escalation_level == 3
    assert stalled.terminal_status is None


def test_infrastructure_interruption_resumes_same_execution_identity():
    decision = advance_example("C", "S", "E", 2, AttemptOutcome.INFRA_INTERRUPTION)
    assert decision.action == "RESUME"
    assert decision.next_escalation_level == 2
    assert decision.execution_id == "C:S:E:L2"


def test_success_after_escalation_is_recorded_as_recovered_completion():
    base = advance_example("C", "S", "E", 0, AttemptOutcome.CORRECT)
    assert base.terminal_status == "PASS"
    recovered = advance_example("C", "S", "E", 2, AttemptOutcome.CORRECT)
    assert recovered.action == "ADVANCE"
    assert recovered.terminal_status == "RECOVERED_BY_ESCALATION"
