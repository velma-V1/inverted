import os
import sys
from pathlib import Path

from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.arming import ArmState
from inverted.system_harvest.environment import EnvironmentPolicy
from inverted.system_harvest.launch import build_launch_envelope
from inverted.system_harvest.process_engine import ProcessEngine, ProcessTermination
from inverted.system_harvest.schedule import ExecutionCell, VerificationContract


TARGET = Path(__file__).parent / "fixtures" / "system_harvest_synthetic_target.py"


def _cell():
    return ExecutionCell.create(
        system_id="Codex", adapter_id="codex", behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fx", fixture_sha256="a" * 64,
        task_contract="synthetic", original_instructions="synthetic",
        active_ingredients=("base",), execution_mode="exec_jsonl", model_runtime_id="synthetic",
        verification=VerificationContract("v", "DETERMINISTIC", ("exit",)), seed_id="s",
        required_artifact_ids=("codex.exec_jsonl",), required_evidence_channels=("MODEL_IO",),
        escalation_route_id="r",
    )


def _envelope(tmp_path, mode, *extra, timeout=2.0, no_progress=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    argv = (sys.executable, str(TARGET.resolve()), mode, *map(str, extra))
    return build_launch_envelope(
        campaign_id="C", cell=_cell(), execution_id=f"E-{mode}", escalation_level=0,
        adapter=adapter_by_id("codex"), workspace=tmp_path.resolve(), run_dir=(tmp_path / "run").resolve(),
        arm_state=ArmState.ARMED_LIVE, substitutions={}, source_identity="synthetic@1",
        environment_fingerprints={}, timeout_seconds=timeout, no_progress_seconds=no_progress,
        permission_policy="synthetic", argv_override=argv,
    )
def _joined(result, source):
    return b"".join(item.persisted_bytes for item in result.observations if item.source == source)


def test_process_engine_captures_stdout_stderr_and_stdin_order(tmp_path):
    engine = ProcessEngine()
    result = engine.run(
        _envelope(tmp_path, "streams"), environment=dict(os.environ), stdin_bytes=b"task-line\n",
        environment_policy=EnvironmentPolicy(secret_names=(), salt="s"),
    )
    assert result.termination is ProcessTermination.EXITED
    assert result.exit_code == 0
    assert result.capture_opened_before_stdin
    assert b'{"event":"one"}' in _joined(result, "stdout")
    assert b"stdin:task-line\n" in _joined(result, "stdout")
    assert b"{malformed-json\n" in _joined(result, "stdout")
    assert b"err-one\n" in _joined(result, "stderr")
    assert Path(result.stdout_capture_path).read_bytes() == _joined(result, "stdout")
    assert Path(result.stderr_capture_path).read_bytes() == _joined(result, "stderr")


def test_process_engine_redacts_secret_even_across_stream_chunks(tmp_path):
    secret = "cross-chunk-super-secret"
    env = dict(os.environ)
    env["SYNTH_SECRET"] = secret
    policy = EnvironmentPolicy(secret_names=("SYNTH_SECRET",), salt="campaign")
    result = ProcessEngine().run(_envelope(tmp_path, "secret"), environment=env, stdin_bytes=b"",
                                 environment_policy=policy, read_chunk_size=5)
    captured = Path(result.stdout_capture_path).read_bytes()
    assert secret.encode() not in captured
    assert b"<REDACTED:SYNTH_SECRET:" in captured
    assert any(item.redactions for item in result.observations if item.source == "stdout")


def test_process_engine_classifies_timeout_without_semantic_verdict(tmp_path):
    result = ProcessEngine().run(
        _envelope(tmp_path, "sleep", 1.0, timeout=0.15), environment=dict(os.environ), stdin_bytes=b"",
        environment_policy=EnvironmentPolicy(secret_names=(), salt="s"),
    )
    assert result.termination is ProcessTermination.TIMEOUT
    assert result.semantic_verdict is None


def test_process_engine_classifies_no_progress_separately(tmp_path):
    result = ProcessEngine().run(
        _envelope(tmp_path, "sleep", 1.0, timeout=2.0, no_progress=0.15),
        environment=dict(os.environ), stdin_bytes=b"",
        environment_policy=EnvironmentPolicy(secret_names=(), salt="s"),
    )
    assert result.termination is ProcessTermination.NO_PROGRESS
    assert b"started\n" in _joined(result, "stdout")


def test_process_engine_preserves_partial_output_and_nonzero_exit(tmp_path):
    partial = ProcessEngine().run(
        _envelope(tmp_path / "p", "partial"), environment=dict(os.environ), stdin_bytes=b"",
        environment_policy=EnvironmentPolicy(secret_names=(), salt="s"),
    )
    assert _joined(partial, "stdout") == b"partial-without-newline"
    failed = ProcessEngine().run(
        _envelope(tmp_path / "e", "exit3"), environment=dict(os.environ), stdin_bytes=b"",
        environment_policy=EnvironmentPolicy(secret_names=(), salt="s"),
    )
    assert failed.termination is ProcessTermination.NONZERO_EXIT
    assert failed.exit_code == 3
