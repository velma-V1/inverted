from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.adapters.registry import all_adapters
from inverted.system_harvest.backend import BackendObservation, BackendResult, FakeExecutionBackend, FakeExecutionScript
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.orchestrator import CampaignOrchestrator, CompletionGates, evaluate_orchestrator_completion
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell(adapter, index):
    return ExecutionCell.create(
        system_id=adapter.descriptor.system_id, adapter_id=adapter.descriptor.adapter_id,
        behavioral_case="TRIVIAL_EDIT", perturbations=(), workspace_fixture_id=f"fx-{index}",
        fixture_sha256=f"{index + 1:064x}", task_contract="task", original_instructions="instructions",
        active_ingredients=("base",), execution_mode="fake", model_runtime_id="fake-model",
        verification=VerificationContract("v", "DETERMINISTIC", ("pass",)), seed_id="seed",
        required_artifact_ids=tuple(a.artifact_id for a in adapter.descriptor.native_artifacts if a.required),
        required_evidence_channels=adapter.descriptor.declared_channels, escalation_route_id="route",
    )


def _script(cell):
    observations = tuple(
        BackendObservation("stream" if aid.endswith("jsonl") else "artifact", aid, f"{aid}\n", aid, i, "text")
        for i, aid in enumerate(cell.required_artifact_ids, 1)
    )
    return FakeExecutionScript(observations, BackendResult(AttemptOutcome.CORRECT, "session", {"verdict": "PASS"}))


def test_all_eleven_adapters_run_under_identical_fake_orchestrator_semantics(tmp_path):
    adapters = all_adapters()
    cells = tuple(_cell(adapter, index) for index, adapter in enumerate(adapters))
    backend = FakeExecutionBackend({(cell.cell_id, 0): _script(cell) for cell in cells})
    preflight = {adapter.descriptor.adapter_id: PreflightReport(True, (), ()) for adapter in adapters}
    orchestrator = CampaignOrchestrator(CampaignSchedule("C", cells, (), "baseline"), backend, tmp_path, preflight)
    states = [orchestrator.run_next_eligible() for _ in cells]
    assert len(states) == 11
    assert all(state.state.value == "COMPLETE" for state in states)
    report = evaluate_orchestrator_completion(
        orchestrator,
        CompletionGates(True, True, True, True),
    )
    assert report.complete is True
    assert report.blockers == ()
    assert len(backend.calls) == 11
