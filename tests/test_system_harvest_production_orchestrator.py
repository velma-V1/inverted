from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.backend import BackendResult, FakeExecutionBackend, FakeExecutionScript
from inverted.system_harvest.escalation import REQUIRED_ESCALATION_SECTIONS, SnapshotSection, SnapshotSectionStatus
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.orchestrator import (
    CampaignOrchestrator, CellState, EscalationRoute, FakeEscalationRouter,
)
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell():
    return ExecutionCell.create(
        system_id="Codex", adapter_id="codex", behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256="a" * 64,
        task_contract="task", original_instructions="instructions", active_ingredients=("base",),
        execution_mode="exec_jsonl", model_runtime_id="weak-model",
        verification=VerificationContract("v", "DETERMINISTIC", ("check",)), seed_id="s",
        required_artifact_ids=("codex.exec_jsonl",), required_evidence_channels=("MODEL_IO",),
        escalation_route_id="route",
    )


def _sections(*args):
    return tuple(
        SnapshotSection(name, SnapshotSectionStatus.CAPTURED, {"name": name}, (f"ev-{name}",), None)
        for name in REQUIRED_ESCALATION_SECTIONS
    )
def test_external_verifier_provider_supplies_semantic_verdict(tmp_path):
    cell = _cell()
    backend = FakeExecutionBackend({
        (cell.cell_id, 0): FakeExecutionScript((), BackendResult(AttemptOutcome.COMPLETED, None, {
            "semantic_verdict": None, "process_exit_code": 0,
        }))
    })
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), backend, tmp_path,
        {"codex": PreflightReport(True, (), ())},
        verifier_provider=lambda cell, result: {"verdict": "PASS", "checks": ["synthetic"]},
    )
    state = orchestrator.run_next_eligible()
    assert state.state is CellState.SNAPSHOT_AFTER_CAPTURED
    verdicts = [r.payload for r in orchestrator.journal.read_all() if r.kind == "VERIFIER_RECORDED"]
    assert verdicts[-1]["verdict"] == "PASS"
    assert verdicts[-1]["payload"]["checks"] == ["synthetic"]


class CapsuleAwareBackend:
    def __init__(self):
        self.registered = []

    def execute(self, cell_id, execution_id, escalation_level):
        return (), BackendResult(AttemptOutcome.STALL, None, {"stall_detector": {"kind": "synthetic"}})

    def resume(self, *args):
        raise AssertionError("resume not expected")

    def continue_from_escalation(self, *args):
        raise AssertionError("continuation not expected yet")

    def register_escalation_capsule(self, capsule_id, payload):
        self.registered.append((capsule_id, payload))
def test_persisted_capsule_is_registered_with_capable_backend_before_routing(tmp_path):
    cell = _cell()
    backend = CapsuleAwareBackend()
    router = FakeEscalationRouter({
        1: EscalationRoute(("strong-model",), "strong-model", "synthetic", "T2", "runtime-2")
    })
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), backend, tmp_path,
        {"codex": PreflightReport(True, (), ())},
        snapshot_provider=_sections, escalation_router=router,
    )
    state = orchestrator.run_next_eligible()
    assert state.state is CellState.ESCALATION_PENDING
    assert len(backend.registered) == 1
    capsule_id, payload = backend.registered[0]
    assert capsule_id == state.parent_capsule_id
    assert payload["resume_mode"] == "CONTINUE_FROM_FAILURE_BOUNDARY"
    persisted = [r for r in orchestrator.journal.read_all() if r.kind == "ESCALATION_CAPSULE_PERSISTED"]
    routed = [r for r in orchestrator.journal.read_all() if r.kind == "ESCALATION_ROUTED"]
    assert persisted and routed and persisted[-1].sequence < routed[-1].sequence
