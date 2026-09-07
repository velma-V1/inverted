from inverted.system_harvest.completion import evaluate_campaign_completion, evaluate_system_completion
from inverted.system_harvest.coverage import CoverageItem, CoverageLedger, FutureQueryProbe
from inverted.system_harvest.types import CoverageStatus


def _closed_ledger():
    return CoverageLedger(
        (CoverageItem("CONTROL_LOOP", CoverageStatus.CAPTURED),),
        (FutureQueryProbe("unplanned question", ("ev1",), True, False),),
    )


def test_system_completion_requires_all_channels_examples_and_integrity():
    report = evaluate_system_completion(
        _closed_ledger(), ("PASS", "RECOVERED_BY_ESCALATION"),
        present_channels=("MODEL_IO",), required_channels=("MODEL_IO", "TOOL_IO"),
        manifests_verified=True, mechanism_records_complete=True,
        escalation_capsules_verified=True,
    )
    assert report.complete is False
    assert any("TOOL_IO" in blocker for blocker in report.blockers)


def test_unresolved_escalation_prevents_completion():
    report = evaluate_system_completion(
        _closed_ledger(), ("PASS", "ESCALATION_PENDING"),
        present_channels=("MODEL_IO", "TOOL_IO"), required_channels=("MODEL_IO", "TOOL_IO"),
        manifests_verified=True, mechanism_records_complete=True,
        escalation_capsules_verified=True,
    )
    assert report.complete is False
    assert any("ESCALATION_PENDING" in blocker for blocker in report.blockers)


def test_recovered_escalation_is_a_completed_example():
    report = evaluate_system_completion(
        _closed_ledger(), ("PASS", "RECOVERED_BY_ESCALATION"),
        present_channels=("MODEL_IO", "TOOL_IO"), required_channels=("MODEL_IO", "TOOL_IO"),
        manifests_verified=True, mechanism_records_complete=True,
        escalation_capsules_verified=True,
    )
    assert report.complete is True


def test_campaign_requires_every_frozen_system_and_verified_cross_manifest():
    systems = ("A", "B")
    good = evaluate_system_completion(_closed_ledger(), ("PASS",), ("X",), ("X",), True, True, True)
    assert evaluate_campaign_completion(systems, {"A": good}, True).complete is False
    assert evaluate_campaign_completion(systems, {"A": good, "B": good}, False).complete is False
    assert evaluate_campaign_completion(systems, {"A": good, "B": good}, True).complete is True


def test_recovered_escalation_requires_verified_capsule_chain():
    report = evaluate_system_completion(
        _closed_ledger(), ("RECOVERED_BY_ESCALATION",),
        present_channels=("MODEL_IO", "TOOL_IO"), required_channels=("MODEL_IO", "TOOL_IO"),
        manifests_verified=True, mechanism_records_complete=True,
        escalation_capsules_verified=False,
    )
    assert report.complete is False
    assert any("escalation capsule" in blocker for blocker in report.blockers)
