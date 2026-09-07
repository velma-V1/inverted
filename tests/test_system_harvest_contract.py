from pathlib import Path

from inverted.system_harvest import load_harvest_template
from inverted.system_harvest.completion import evaluate_campaign_completion, evaluate_system_completion
from inverted.system_harvest.coverage import CoverageItem, CoverageLedger, FutureQueryProbe
from inverted.system_harvest.execution import AttemptOutcome, advance_example
from inverted.system_harvest.types import CoverageStatus


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = load_harvest_template(ROOT / "configs" / "system-harvest-11" / "campaign.json")


def _complete_report():
    ledger = CoverageLedger(
        tuple(CoverageItem(domain, CoverageStatus.CAPTURED) for domain in TEMPLATE.coverage_domains),
        (FutureQueryProbe("novel cross-system question", ("ev1",), True, False),),
    )
    return evaluate_system_completion(
        ledger, ("PASS", "RECOVERED_BY_ESCALATION"), TEMPLATE.required_evidence_channels,
        TEMPLATE.required_evidence_channels, True, True, True,
    )


def test_semantic_failure_escalates_instead_of_becoming_terminal():
    failed = advance_example("C", TEMPLATE.systems[0], "E", 0, AttemptOutcome.INCORRECT)
    assert failed.action == "CAPTURE_AND_ESCALATE"
    assert failed.terminal_status is None
    assert failed.snapshot_required is True


def test_all_systems_can_complete_after_escalation_recovery():
    reports = {system: _complete_report() for system in TEMPLATE.systems}
    assert evaluate_campaign_completion(TEMPLATE.systems, reports, True).complete is True


def test_new_discovery_reopens_completion_until_resolved():
    base = CoverageLedger((CoverageItem("x", CoverageStatus.CAPTURED),), (FutureQueryProbe("new", ("e",), True, False),))
    reopened = base.add_item(CoverageItem("DISCOVERED:y", CoverageStatus.NEEDS_GAP_CLOSURE))
    report = evaluate_system_completion(reopened, ("PASS",), ("X",), ("X",), True, True, True)
    assert report.complete is False
    closed = reopened.resolve("DISCOVERED:y", CoverageStatus.CAPTURED, evidence_ids=("e2",))
    assert evaluate_system_completion(closed, ("PASS",), ("X",), ("X",), True, True, True).complete is True
