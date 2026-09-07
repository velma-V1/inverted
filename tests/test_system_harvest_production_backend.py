import hashlib
import os
import sys
from pathlib import Path

import pytest

from inverted.system_harvest.arming import ArmState
from inverted.system_harvest.backend import BackendObservation
from inverted.system_harvest.environment import EnvironmentPolicy
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.process_engine import ProcessObservation, ProcessResult, ProcessTermination
from inverted.system_harvest.production_backend import DuplicateLaunchError, ProductionExecutionBackend
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract
from inverted.system_harvest.workspace import tree_hash


TARGET = Path(__file__).parent / "fixtures" / "system_harvest_synthetic_target.py"


class RecordingEngine:
    def __init__(self, termination=ProcessTermination.EXITED):
        self.termination = termination
        self.calls = []

    def run(self, envelope, *, environment, stdin_bytes, environment_policy, read_chunk_size=4096):
        self.calls.append((envelope, stdin_bytes, dict(environment)))
        data = b'{"synthetic":true}\n'
        obs = ProcessObservation("stdout", 0, 0, data, hashlib.sha256(data).hexdigest(), (), 1)
        return ProcessResult(self.termination, 0 if self.termination is ProcessTermination.EXITED else None,
                             123, (obs,), "stdout.bin", "stderr.bin", True)


def _fixture(tmp_path):
    root = tmp_path / "fixture"
    root.mkdir(exist_ok=True)
    (root / "file.txt").write_text("base\n", encoding="utf-8")
    return root


def _cell(fixture):
    return ExecutionCell.create(
        system_id="Codex", adapter_id="codex", behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256=tree_hash(fixture),
        task_contract="synthetic task", original_instructions="synthetic task",
        active_ingredients=("base",), execution_mode="exec_jsonl", model_runtime_id="synthetic-model",
        verification=VerificationContract("v", "DETERMINISTIC", ("exit",)), seed_id="s",
        required_artifact_ids=("codex.exec_jsonl",), required_evidence_channels=("MODEL_IO",),
        escalation_route_id="r",
    )


def _backend(tmp_path, *, engine=None, arm_state=ArmState.ARMED_LIVE):
    fixture = _fixture(tmp_path)
    cell = _cell(fixture)
    schedule = CampaignSchedule("C", (cell,), (), "baseline")
    engine = engine or RecordingEngine()
    backend = ProductionExecutionBackend(
        schedule=schedule, fixture_paths={"fx": fixture}, run_root=tmp_path / "run",
        arm_state=arm_state, environment=dict(os.environ),
        environment_policy=EnvironmentPolicy(secret_names=(), salt="s"),
        source_identities={"codex": "synthetic@1"}, process_engine=engine,
        synthetic_launch_overrides={"codex": (sys.executable, str(TARGET.resolve()), "partial")},
    )
    return backend, cell, engine
def test_execute_maps_process_facts_without_claiming_semantic_correctness(tmp_path):
    backend, cell, engine = _backend(tmp_path)
    observations, result = backend.execute(cell.cell_id, "E0", 0)
    assert len(engine.calls) == 1
    assert result.outcome is AttemptOutcome.COMPLETED
    assert result.verifier_payload["semantic_verdict"] is None
    assert result.verifier_payload["process_exit_code"] == 0
    assert observations[0].raw_bytes == b'{"synthetic":true}\n'
    assert observations[0].raw_text is None


def test_duplicate_idempotency_key_cannot_spawn_twice(tmp_path):
    backend, cell, engine = _backend(tmp_path)
    backend.execute(cell.cell_id, "E0", 0)
    with pytest.raises(DuplicateLaunchError, match="idempotency"):
        backend.execute(cell.cell_id, "E0", 0)
    assert len(engine.calls) == 1


def test_disarmed_backend_rejects_before_process_engine(tmp_path):
    backend, cell, engine = _backend(tmp_path, arm_state=ArmState.DRY_RUN)
    with pytest.raises(Exception, match="ARMED_LIVE"):
        backend.execute(cell.cell_id, "E0", 0)
    assert engine.calls == []


def test_ambiguous_resume_never_blindly_resends(tmp_path):
    backend, cell, engine = _backend(tmp_path)
    observations, result = backend.resume(cell.cell_id, "E0", 0, "unknown-session")
    assert observations == ()
    assert result.outcome is AttemptOutcome.INFRA_INTERRUPTION
    assert result.verifier_payload["recovery_uncertain"] is True
    assert engine.calls == []


def test_escalation_continuation_requires_capsule_and_preserves_boundary_mode(tmp_path):
    backend, cell, engine = _backend(tmp_path)
    backend.execute(cell.cell_id, "E0", 0)
    baseline_workspace = engine.calls[0][0].cwd
    backend.register_escalation_capsule("cap-1", {"continuation_directive": "continue exact state"})
    observations, result = backend.continue_from_escalation(cell.cell_id, "E1", 1, "cap-1", "strong-model")
    assert result.outcome is AttemptOutcome.COMPLETED
    assert result.verifier_payload["resume_mode"] == "CONTINUE_FROM_FAILURE_BOUNDARY"
    assert result.verifier_payload["capsule_id"] == "cap-1"
    assert engine.calls[1][0].escalation_level == 1
    assert engine.calls[1][0].cwd == baseline_workspace
    with pytest.raises(KeyError):
        backend.continue_from_escalation(cell.cell_id, "E2", 2, "missing", "stronger-model")


def test_idempotency_claim_survives_backend_reconstruction(tmp_path):
    backend, cell, engine = _backend(tmp_path)
    backend.execute(cell.cell_id, "E0", 0)
    rebuilt, rebuilt_cell, rebuilt_engine = _backend(tmp_path, engine=RecordingEngine())
    assert rebuilt_cell.cell_id == cell.cell_id
    with pytest.raises(DuplicateLaunchError, match="idempotency"):
        rebuilt.execute(cell.cell_id, "E0", 0)
    assert rebuilt_engine.calls == []
