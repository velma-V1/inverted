from inverted.system_harvest.acquisition import AcquisitionRecorder
from inverted.system_harvest.adapters.preflight import PreflightReport
from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.backend import BackendObservation, FakeExecutionBackend
from inverted.system_harvest.orchestrator import CampaignOrchestrator
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract


def _cell():
    return ExecutionCell.create(
        system_id="Codex", adapter_id="codex", behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256="a" * 64,
        task_contract="t", original_instructions="i", active_ingredients=("base",),
        execution_mode="exec_jsonl", model_runtime_id="m",
        verification=VerificationContract("v", "DETERMINISTIC", ("exit",)), seed_id="s",
        required_artifact_ids=("codex.exec_jsonl",), required_evidence_channels=("MODEL_IO",),
        escalation_route_id="r",
    )


def test_orchestrator_persists_backend_raw_bytes_without_decoding(tmp_path):
    cell = _cell()
    orchestrator = CampaignOrchestrator(
        CampaignSchedule("C", (cell,), (), "baseline"), FakeExecutionBackend({}), tmp_path,
        {"codex": PreflightReport(True, (), ())},
    )
    recorder = AcquisitionRecorder(
        "C", "E0", cell.cell_id, adapter_by_id("codex"), tmp_path / "record",
        PreflightReport(True, (), ()),
    )
    raw = b'\xff{"broken":true}\x00\n'
    observation = BackendObservation(
        "stream", "codex.exec_jsonl", None, "process:stdout", 0, "binary", raw_bytes=raw,
    )
    orchestrator._persist_observation(recorder, observation)
    assert recorder.stream_path("codex.exec_jsonl").read_bytes() == raw
