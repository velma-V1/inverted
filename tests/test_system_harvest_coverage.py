import pytest

from inverted.system_harvest.coverage import CoverageItem, CoverageLedger, FutureQueryProbe
from inverted.system_harvest.types import CoverageStatus


def test_new_discovery_appends_without_mutating_prior_ledger():
    base = CoverageLedger((CoverageItem("CONTROL_LOOP", CoverageStatus.CAPTURED),))
    expanded = base.add_item(CoverageItem("DISCOVERED:hidden-threshold", CoverageStatus.NEEDS_GAP_CLOSURE))
    assert len(base.items) == 1
    assert len(expanded.items) == 2
    assert expanded.is_open is True


def test_partial_and_needs_states_keep_ledger_open():
    for status in (CoverageStatus.PENDING, CoverageStatus.CAPTURED_PARTIAL,
                   CoverageStatus.NEEDS_RUNTIME_PROBE, CoverageStatus.NEEDS_STATIC_PROBE,
                   CoverageStatus.NEEDS_GAP_CLOSURE):
        assert CoverageLedger((CoverageItem("x", status),)).is_open is True


def test_inaccessible_requires_reason_and_evidence():
    ledger = CoverageLedger((CoverageItem("x", CoverageStatus.PENDING),))
    with pytest.raises(ValueError, match="INACCESSIBLE"):
        ledger.resolve("x", CoverageStatus.INACCESSIBLE, reason="not exposed", evidence_ids=())
    closed = ledger.resolve("x", CoverageStatus.INACCESSIBLE, reason="provider does not expose it", evidence_ids=("ev1",))
    assert closed.is_open is False


def test_future_query_probe_must_be_new_and_passed():
    ledger = CoverageLedger((CoverageItem("x", CoverageStatus.CAPTURED),))
    assert ledger.future_query_ready is False
    ledger = ledger.add_future_query(FutureQueryProbe("new question", ("ev1",), passed=True, predefined=False))
    assert ledger.future_query_ready is True
