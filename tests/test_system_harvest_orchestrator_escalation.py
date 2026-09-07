from pathlib import Path

from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.backend import BackendObservation, BackendResult, FakeExecutionBackend, FakeExecutionScript
from inverted.system_harvest.escalation import REQUIRED_ESCALATION_SECTIONS, SnapshotSection, SnapshotSectionStatus
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.journal import HarvestJournal
from inverted.system_harvest.orchestrator import (
    CampaignOrchestrator, CellState, EscalationRoute, FakeEscalationRouter,
)
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell():
    adapter = adapter_by_id("codex")
    return ExecutionCell.create(
        system_id=adapter.descriptor.system_id, adapter_id="codex", behavioral_case="DEBUGGING",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256="b" * 64,
        task_contract="debug", original_instructions="debug and verify", active_ingredients=("base",),
        execution_mode="fake", model_runtime_id="weak-model", verification=VerificationContract("v", "DETERMINISTIC", ("pass",)),
        seed_id="s", required_artifact_ids=tuple(a.artifact_id for a in adapter.descriptor.native_artifacts if a.required),
        required_evidence_channels=adapter.descriptor.declared_channels, escalation_route_id="route",
    )


def _sections(cell, result, boundary_kind, level):
    return tuple(
        SnapshotSection(name, SnapshotSectionStatus.CAPTURED,
                        {"boundary": boundary_kind, "level": level, "cell": cell.cell_id},
                        (f"evidence-{level}-{name}",), None)
        for name in REQUIRED_ESCALATION_SECTIONS
    )


def _required_observations(cell, prefix):
    return tuple(
        BackendObservation("stream" if artifact_id.endswith("jsonl") else "artifact",
                           artifact_id, f"{prefix}-{artifact_id}\n", artifact_id, i, "text")
        for i, artifact_id in enumerate(cell.required_artifact_ids, 1)
    )


def _orchestrator(tmp_path, scripts):
    cell = _cell()
    router = FakeEscalationRouter({
        1: EscalationRoute(("frontier-1",), "frontier-1", "tier rule", "FRONTIER", "runtime-1"),
        2: EscalationRoute(("frontier-2",), "frontier-2", "tier rule", "FRONTIER_PLUS", "runtime-2"),
    })
    backend = FakeExecutionBackend(scripts)
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), backend, tmp_path,
        {"codex": PreflightReport(True, (), ())}, snapshot_provider=_sections, escalation_router=router,
    )
    return cell, backend, orchestrator


def test_incorrect_persists_verified_capsule_before_router_and_continues_boundary(tmp_path):
    cell = _cell()
    scripts = {
        (cell.cell_id, 0): FakeExecutionScript(_required_observations(cell, "bad"), BackendResult(AttemptOutcome.INCORRECT, "s0", {"verdict": "INCORRECT"})),
        (cell.cell_id, 1): FakeExecutionScript(_required_observations(cell, "good"), BackendResult(AttemptOutcome.CORRECT, "s1", {"verdict": "PASS"})),
    }
    _, backend, orchestrator = _orchestrator(tmp_path, scripts)
    first = orchestrator.run_next_eligible()
    assert first.state is CellState.ESCALATION_PENDING
    assert first.escalation_level == 1
    records = HarvestJournal(tmp_path / "orchestrator.jsonl", "C").read_all()
    kinds = [r.kind for r in records]
    assert kinds.index("ESCALATION_CAPSULE_PERSISTED") < kinds.index("ESCALATION_ROUTED")
    second = orchestrator.run_next_eligible()
    assert second.state is CellState.COMPLETE
    assert second.terminal_status == "RECOVERED_BY_ESCALATION"
    assert backend.calls[-1][0] == "ESCALATE"


def test_stall_records_detector_evidence_before_capsule(tmp_path):
    cell = _cell()
    scripts = {(cell.cell_id, 0): FakeExecutionScript(
        _required_observations(cell, "stall"),
        BackendResult(AttemptOutcome.STALL, "s0", {"stall_detector": {"rule": "no_progress", "threshold": 30}}),
    )}
    _, _, orchestrator = _orchestrator(tmp_path, scripts)
    state = orchestrator.run_next_eligible()
    assert state.state is CellState.ESCALATION_PENDING
    kinds = [r.kind for r in HarvestJournal(tmp_path / "orchestrator.jsonl", "C").read_all()]
    assert kinds.index("STALL_VERDICT_RECORDED") < kinds.index("ESCALATION_CAPSULE_PERSISTED")


def test_recursive_escalation_links_child_capsule_to_parent(tmp_path):
    cell = _cell()
    scripts = {
        (cell.cell_id, 0): FakeExecutionScript(_required_observations(cell, "l0"), BackendResult(AttemptOutcome.INCORRECT, "s0", {"verdict": "INCORRECT"})),
        (cell.cell_id, 1): FakeExecutionScript(_required_observations(cell, "l1"), BackendResult(AttemptOutcome.STALL, "s1", {"stall_detector": {"rule": "repeat"}})),
        (cell.cell_id, 2): FakeExecutionScript(_required_observations(cell, "l2"), BackendResult(AttemptOutcome.CORRECT, "s2", {"verdict": "PASS"})),
    }
    _, _, orchestrator = _orchestrator(tmp_path, scripts)
    first = orchestrator.run_next_eligible()
    parent = first.parent_capsule_id
    assert parent
    second = orchestrator.run_next_eligible()
    child = second.parent_capsule_id
    assert second.state is CellState.ESCALATION_PENDING
    assert child and child != parent
    capsule_records = [r for r in HarvestJournal(tmp_path / "orchestrator.jsonl", "C").read_all() if r.kind == "ESCALATION_CAPSULE_PERSISTED"]
    assert capsule_records[1].payload["parent_capsule_id"] == parent
    final = orchestrator.run_next_eligible()
    assert final.state is CellState.COMPLETE


def test_restart_from_escalation_pending_does_not_duplicate_capsule_or_restart_source(tmp_path):
    cell = _cell()
    scripts = {
        (cell.cell_id, 0): FakeExecutionScript(_required_observations(cell, "bad"), BackendResult(AttemptOutcome.INCORRECT, "s0", {"verdict": "INCORRECT"})),
        (cell.cell_id, 1): FakeExecutionScript(_required_observations(cell, "good"), BackendResult(AttemptOutcome.CORRECT, "s1", {"verdict": "PASS"})),
    }
    _, backend, first = _orchestrator(tmp_path, scripts)
    assert first.run_next_eligible().state is CellState.ESCALATION_PENDING
    router = FakeEscalationRouter({1: EscalationRoute(("frontier-1",), "frontier-1", "tier rule", "FRONTIER", "runtime-1")})
    restarted = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), backend, tmp_path,
        {"codex": PreflightReport(True, (), ())}, snapshot_provider=_sections, escalation_router=router,
    )
    final = restarted.run_next_eligible()
    assert final.state is CellState.COMPLETE
    records = HarvestJournal(tmp_path / "orchestrator.jsonl", "C").read_all()
    assert len([r for r in records if r.kind == "ESCALATION_CAPSULE_PERSISTED"]) == 1
    assert [call[0] for call in backend.calls] == ["START", "ESCALATE"]
