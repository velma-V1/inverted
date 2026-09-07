from pathlib import Path

import pytest

from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.backend import BackendObservation, BackendResult, FakeExecutionBackend, FakeExecutionScript
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.journal import HarvestJournal
from inverted.system_harvest.orchestrator import CampaignOrchestrator, CellState
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell(adapter_id="codex"):
    adapter = adapter_by_id(adapter_id)
    return ExecutionCell.create(
        system_id=adapter.descriptor.system_id, adapter_id=adapter_id, behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256="a" * 64,
        task_contract="change x", original_instructions="change x and verify", active_ingredients=("base",),
        execution_mode="fake", model_runtime_id="fake-model", verification=VerificationContract("v", "DETERMINISTIC", ("pass",)),
        seed_id="s", required_artifact_ids=tuple(a.artifact_id for a in adapter.descriptor.native_artifacts if a.required),
        required_evidence_channels=adapter.descriptor.declared_channels, escalation_route_id="route",
    )


def _schedule(cell):
    return CampaignSchedule("C", (cell,), (), "baseline")


def _success_script(cell):
    observations = []
    for index, artifact_id in enumerate(cell.required_artifact_ids, 1):
        kind = "stream" if artifact_id.endswith("jsonl") else "artifact"
        observations.append(BackendObservation(kind, artifact_id, f"fixture-{artifact_id}\n", artifact_id, index, "text"))
    return FakeExecutionScript(tuple(observations), BackendResult(AttemptOutcome.CORRECT, "session", {"verdict": "PASS"}))


def test_no_backend_launch_before_global_and_cell_preflight(tmp_path):
    cell = _cell()
    backend = FakeExecutionBackend({(cell.cell_id, 0): _success_script(cell)})
    orchestrator = CampaignOrchestrator(_schedule(cell), backend, tmp_path, {"codex": PreflightReport(False, ("blocked",), ())})
    with pytest.raises(RuntimeError, match="preflight"):
        orchestrator.run_next_eligible()
    assert backend.calls == ()


def test_success_path_persists_raw_before_verification_and_completes_after_manifest(tmp_path):
    cell = _cell()
    backend = FakeExecutionBackend({(cell.cell_id, 0): _success_script(cell)})
    orchestrator = CampaignOrchestrator(_schedule(cell), backend, tmp_path, {"codex": PreflightReport(True, (), ())})
    state = orchestrator.run_next_eligible()
    assert state.state is CellState.COMPLETE
    records = HarvestJournal(tmp_path / "orchestrator.jsonl", "C").read_all()
    kinds = [record.kind for record in records]
    assert kinds.index("BACKEND_OBSERVATION_PERSISTED") < kinds.index("VERIFIER_RECORDED")
    assert kinds.index("SNAPSHOT_AFTER_CAPTURED") < kinds.index("CELL_COMPLETED")
    assert "ARTIFACT_MANIFEST_VERIFIED" in kinds


def test_blocked_cell_does_not_abort_unrelated_eligible_cell(tmp_path):
    blocked = _cell("codex")
    eligible = _cell("claude_code")
    backend = FakeExecutionBackend({(eligible.cell_id, 0): _success_script(eligible)})
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (blocked, eligible), (), "baseline"), backend, tmp_path,
        {"codex": PreflightReport(False, ("blocked",), ()), "claude_code": PreflightReport(True, (), ())},
    )
    state = orchestrator.run_next_eligible()
    assert state.cell_id == eligible.cell_id
    assert state.state is CellState.COMPLETE
    assert backend.calls[0][1] == eligible.cell_id
