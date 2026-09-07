from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.backend import BackendResult, FakeExecutionBackend, FakeExecutionScript
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.orchestrator import (
    CampaignOrchestrator, CellState, CompletionGates, evaluate_orchestrator_completion,
)
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell():
    adapter = adapter_by_id("codex")
    return ExecutionCell.create(
        system_id=adapter.descriptor.system_id, adapter_id="codex", behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256="e" * 64,
        task_contract="task", original_instructions="instructions", active_ingredients=("base",),
        execution_mode="fake", model_runtime_id="m", verification=VerificationContract("v", "DETERMINISTIC", ("pass",)),
        seed_id="s", required_artifact_ids=tuple(a.artifact_id for a in adapter.descriptor.native_artifacts if a.required),
        required_evidence_channels=adapter.descriptor.declared_channels, escalation_route_id="route",
    )


def _gates(**overrides):
    values = dict(future_query_ready=True, cross_system_manifest_verified=True,
                  system_reports_verified=True, evidence_coverage_verified=True)
    values.update(overrides)
    return CompletionGates(**values)


def test_scheduler_exhaustion_or_open_cell_cannot_report_complete(tmp_path):
    cell = _cell()
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), FakeExecutionBackend({}), tmp_path,
        {"codex": PreflightReport(True, (), ())},
    )
    report = evaluate_orchestrator_completion(orchestrator, _gates())
    assert report.complete is False
    assert any("cell not complete" in blocker for blocker in report.blockers)


def test_external_evidence_gates_block_completion_even_if_cell_state_is_complete(tmp_path):
    cell = _cell()
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), FakeExecutionBackend({}), tmp_path,
        {"codex": PreflightReport(True, (), ())},
    )
    orchestrator._states[cell.cell_id] = orchestrator._states[cell.cell_id].__class__(
        cell.cell_id, CellState.COMPLETE, 0, "exec", "session", True, "PASS", None, None
    )
    report = evaluate_orchestrator_completion(orchestrator, _gates(future_query_ready=False))
    assert report.complete is False
    assert "future query gate not ready" in report.blockers
