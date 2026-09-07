import os
import sys
from pathlib import Path

from inverted.system_harvest.adapters.registry import adapter_by_id, all_adapters
from inverted.system_harvest.arming import ArmState
from inverted.system_harvest.drivers.registry import all_drivers
from inverted.system_harvest.environment import EnvironmentPolicy
from inverted.system_harvest.execution import AttemptOutcome
from inverted.system_harvest.process_engine import ProcessEngine
from inverted.system_harvest.production_backend import ProductionExecutionBackend
from inverted.system_harvest.schedule import CampaignSchedule, ExecutionCell, VerificationContract
from inverted.system_harvest.workspace import tree_hash

TARGET = Path(__file__).parent / "fixtures" / "system_harvest_synthetic_target.py"


class RecordingProcessEngine:
    def __init__(self):
        self.calls = []
        self.inner = ProcessEngine()

    def run(self, envelope, **kwargs):
        self.calls.append(envelope)
        return self.inner.run(envelope, **kwargs)


def _fixture(tmp_path):
    root = tmp_path / "fixture"
    root.mkdir(exist_ok=True)
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    return root
def _cell(fixture, adapter_id):
    adapter = adapter_by_id(adapter_id)
    driver = next(item for item in all_drivers() if item.descriptor.adapter_id == adapter_id)
    first_artifact = adapter.descriptor.native_artifacts[0].artifact_id
    return ExecutionCell.create(
        system_id=adapter.descriptor.system_id, adapter_id=adapter_id,
        behavioral_case="TRIVIAL_EDIT", perturbations=(), workspace_fixture_id="fx",
        fixture_sha256=tree_hash(fixture), task_contract="synthetic",
        original_instructions="synthetic", active_ingredients=("base",),
        execution_mode=driver.descriptor.task_mode_id, model_runtime_id="synthetic-model",
        verification=VerificationContract("v", "DETERMINISTIC", ("exit",)), seed_id="s",
        required_artifact_ids=(first_artifact,), required_evidence_channels=("MODEL_IO",),
        escalation_route_id="r",
    )


def _backend(tmp_path, adapter_ids, mode="partial", *, environment=None, policy=None,
             timeout=2.0, overrides=None):
    fixture = _fixture(tmp_path)
    cells = tuple(_cell(fixture, adapter_id) for adapter_id in adapter_ids)
    schedule = CampaignSchedule("C", cells, (), "baseline")
    engine = RecordingProcessEngine()
    launch_overrides = overrides or {
        adapter_id: (sys.executable, str(TARGET.resolve()), mode) for adapter_id in adapter_ids
    }
    backend = ProductionExecutionBackend(
        schedule=schedule, fixture_paths={"fx": fixture}, run_root=tmp_path / "run",
        arm_state=ArmState.ARMED_LIVE, environment=environment or dict(os.environ),
        environment_policy=policy or EnvironmentPolicy(secret_names=(), salt="s"),
        source_identities={adapter_id: "synthetic@1" for adapter_id in adapter_ids},
        process_engine=engine, synthetic_launch_overrides=launch_overrides,
        timeout_seconds=timeout,
    )
    return backend, cells, engine
def test_all_11_drivers_use_only_synthetic_local_executable(tmp_path):
    adapter_ids = tuple(adapter.descriptor.adapter_id for adapter in all_adapters())
    backend, cells, engine = _backend(tmp_path, adapter_ids)
    assert len(cells) == 11
    for index, cell in enumerate(cells):
        observations, result = backend.execute(cell.cell_id, f"E{index}", 0)
        assert result.outcome is AttemptOutcome.COMPLETED
        assert observations
    assert len(engine.calls) == 11
    assert all(call.argv[0] == sys.executable for call in engine.calls)
    forbidden = {"codex", "claude", "prime-agent", "pi", "oh-my-cli", "sweagent", "mini", "aider", "openhands", "kimi", "cargo"}
    assert all(Path(call.argv[0]).name.lower() not in forbidden for call in engine.calls)


def test_malformed_native_bytes_survive_production_backend(tmp_path):
    backend, (cell,), _ = _backend(tmp_path, ("codex",), mode="streams")
    observations, result = backend.execute(cell.cell_id, "E-malformed", 0)
    assert result.outcome is AttemptOutcome.COMPLETED
    raw = b"".join(item.raw_bytes or b"" for item in observations)
    assert b"{malformed-json\n" in raw


def test_secret_echo_is_redacted_before_backend_observation(tmp_path):
    secret = "super-secret-value"
    env = dict(os.environ)
    env["SYNTH_SECRET"] = secret
    policy = EnvironmentPolicy(secret_names=("SYNTH_SECRET",), salt="s")
    backend, (cell,), _ = _backend(tmp_path, ("codex",), mode="secret", environment=env, policy=policy)
    observations, _ = backend.execute(cell.cell_id, "E-secret", 0)
    raw = b"".join(item.raw_bytes or b"" for item in observations)
    assert secret.encode() not in raw
    assert b"<REDACTED:SYNTH_SECRET:" in raw
def test_timeout_preserves_partial_output_and_is_infrastructure_interruption(tmp_path):
    overrides = {"codex": (sys.executable, str(TARGET.resolve()), "sleep", "0.5")}
    backend, (cell,), _ = _backend(tmp_path, ("codex",), timeout=0.05, overrides=overrides)
    observations, result = backend.execute(cell.cell_id, "E-timeout", 0)
    assert result.outcome is AttemptOutcome.INFRA_INTERRUPTION
    assert b"started\n" in b"".join(item.raw_bytes or b"" for item in observations)


def test_planned_and_unexpected_run_artifacts_are_returned(tmp_path):
    overrides = {
        "codex": (
            sys.executable, str(TARGET.resolve()), "artifact",
            "{run_dir}/native/codex/exec.jsonl", "{run_dir}/surprise.bin",
        )
    }
    backend, (cell,), _ = _backend(tmp_path, ("codex",), overrides=overrides)
    observations, result = backend.execute(cell.cell_id, "E-artifacts", 0)
    assert result.outcome is AttemptOutcome.COMPLETED
    artifacts = [item for item in observations if item.kind == "artifact"]
    assert any(item.artifact_id == "codex.exec_jsonl" for item in artifacts)
    assert any(item.artifact_id.startswith("discovered:") for item in artifacts)
    discovered = next(item for item in artifacts if item.artifact_id.startswith("discovered:"))
    assert discovered.raw_bytes == b"surprise-bytes\x00\xff"
