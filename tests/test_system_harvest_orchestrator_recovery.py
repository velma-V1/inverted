from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.backend import BackendObservation, BackendResult, FakeExecutionBackend, FakeExecutionScript
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.orchestrator import CampaignOrchestrator, CellState
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell(name="TRIVIAL_EDIT", salt="c"):
    adapter = adapter_by_id("codex")
    return ExecutionCell.create(
        system_id=adapter.descriptor.system_id, adapter_id="codex", behavioral_case=name,
        perturbations=(), workspace_fixture_id=f"fx-{salt}", fixture_sha256=salt * 64,
        task_contract="task", original_instructions="instructions", active_ingredients=("base",),
        execution_mode="fake", model_runtime_id="m", verification=VerificationContract("v", "DETERMINISTIC", ("pass",)),
        seed_id="s", required_artifact_ids=tuple(a.artifact_id for a in adapter.descriptor.native_artifacts if a.required),
        required_evidence_channels=adapter.descriptor.declared_channels, escalation_route_id="route",
    )


def _success(cell):
    obs = tuple(BackendObservation("stream" if aid.endswith("jsonl") else "artifact", aid, f"{aid}\n", aid, i, "text")
                for i, aid in enumerate(cell.required_artifact_ids, 1))
    return FakeExecutionScript(obs, BackendResult(AttemptOutcome.CORRECT, "session", {"verdict": "PASS"}))


def test_infrastructure_interruption_resumes_same_execution_id_and_level(tmp_path):
    cell = _cell()
    interrupted = FakeExecutionScript((), BackendResult(AttemptOutcome.INFRA_INTERRUPTION, "session-r", {}))
    backend = FakeExecutionBackend({(cell.cell_id, 0): (interrupted, _success(cell))})
    orchestrator = CampaignOrchestrator(CampaignSchedule("C", (cell,), (), "baseline"), backend, tmp_path,
                                        {"codex": PreflightReport(True, (), ())})
    first = orchestrator.run_next_eligible()
    execution_id = first.execution_id
    assert first.state is CellState.INFRA_INTERRUPTED
    second = orchestrator.run_next_eligible()
    assert second.state is CellState.COMPLETE
    assert second.execution_id == execution_id
    assert second.escalation_level == 0
    assert backend.calls[0][0] == "START"
    assert backend.calls[1] == ("RESUME", cell.cell_id, execution_id, 0, "session-r")


def test_restart_replays_journal_and_resumes_without_duplicate_start(tmp_path):
    cell = _cell()
    interrupted = FakeExecutionScript((), BackendResult(AttemptOutcome.INFRA_INTERRUPTION, "session-r", {}))
    backend = FakeExecutionBackend({(cell.cell_id, 0): (interrupted, _success(cell))})
    schedule = CampaignSchedule("C", (cell,), (), "baseline")
    first = CampaignOrchestrator(schedule, backend, tmp_path, {"codex": PreflightReport(True, (), ())})
    first_state = first.run_next_eligible()
    restarted = CampaignOrchestrator(schedule, backend, tmp_path, {"codex": PreflightReport(True, (), ())})
    assert restarted.runtime_state.by_id(cell.cell_id).state is CellState.INFRA_INTERRUPTED
    final = restarted.run_next_eligible()
    assert final.execution_id == first_state.execution_id
    assert [call[0] for call in backend.calls] == ["START", "RESUME"]


def test_unknown_interruption_completion_becomes_recovery_uncertain(tmp_path):
    cell = _cell()
    backend = FakeExecutionBackend({
        (cell.cell_id, 0): FakeExecutionScript((), BackendResult(AttemptOutcome.INFRA_INTERRUPTION, None, {}))
    })
    orchestrator = CampaignOrchestrator(CampaignSchedule("C", (cell,), (), "baseline"), backend, tmp_path,
                                        {"codex": PreflightReport(True, (), ())})
    assert orchestrator.run_next_eligible().state is CellState.INFRA_INTERRUPTED
    state = orchestrator.run_next_eligible()
    assert state.state is CellState.RECOVERY_UNCERTAIN
    assert len(backend.calls) == 1


def test_admitted_supplemental_cell_preserves_baseline_and_becomes_mandatory(tmp_path):
    cell = _cell()
    schedule = CampaignSchedule("C", (cell,), (), "baseline-hash")
    orchestrator = CampaignOrchestrator(schedule, FakeExecutionBackend({}), tmp_path,
                                        {"codex": PreflightReport(True, (), ())})
    supplemental = _cell("DEBUGGING", "d")
    updated = orchestrator.admit_supplemental(
        supplemental, origin_evidence_ids=("ev-1",), discovery="new loop",
        decision_value="changes recovery", closure_condition="explain loop",
    )
    assert updated.baseline_sha256 == "baseline-hash"
    assert updated.baseline_cells == (cell,)
    assert updated.supplemental_cells[0].cell == supplemental
    assert orchestrator.runtime_state.by_id(supplemental.cell_id).state is CellState.PLANNED
