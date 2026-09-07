from pathlib import Path

import pytest

from inverted.system_harvest.adapters.registry import adapter_by_id
from inverted.system_harvest.arming import ArmState
from inverted.system_harvest.launch import LaunchEnvelopeError, build_launch_envelope, validate_launch_envelope
from inverted.system_harvest.schedule import ExecutionCell, VerificationContract


def _cell(mode="exec_jsonl"):
    return ExecutionCell.create(
        system_id="Codex", adapter_id="codex", behavioral_case="TRIVIAL_EDIT",
        perturbations=(), workspace_fixture_id="fixture", fixture_sha256="a" * 64,
        task_contract="change one file", original_instructions="do the task",
        active_ingredients=("base",), execution_mode=mode, model_runtime_id="model-x",
        verification=VerificationContract("v", "DETERMINISTIC", ("exit=0",)),
        seed_id="s1", required_artifact_ids=("codex.exec_jsonl",),
        required_evidence_channels=("MODEL_IO",), escalation_route_id="route",
    )


def _kwargs(tmp_path, **extra):
    values = dict(
        campaign_id="C", cell=_cell(), execution_id="E", escalation_level=0,
        adapter=adapter_by_id("codex"), workspace=tmp_path.resolve(), run_dir=(tmp_path / "run").resolve(),
        arm_state=ArmState.ARMED_LIVE, substitutions={"task": "edit it"},
        source_identity="codex@test", environment_fingerprints={"PATH": "fp"},
        timeout_seconds=30.0, permission_policy="noninteractive",
    )
    values.update(extra)
    return values
def test_task_bearing_launch_requires_armed_live(tmp_path):
    for state in (ArmState.BUILD, ArmState.DRY_RUN, ArmState.PREFLIGHT_PROBE):
        with pytest.raises(LaunchEnvelopeError, match="ARMED_LIVE"):
            build_launch_envelope(**_kwargs(tmp_path, arm_state=state))


def test_preflight_probe_is_allowlisted_and_contains_no_task(tmp_path):
    envelope = build_launch_envelope(
        **_kwargs(tmp_path, arm_state=ArmState.PREFLIGHT_PROBE, task_bearing=False,
                  probe_argv=("codex", "--version"), probe_kind="version")
    )
    assert envelope.action_kind == "PREFLIGHT_PROBE"
    assert envelope.argv == ("codex", "--version")
    assert validate_launch_envelope(envelope).valid
    with pytest.raises(LaunchEnvelopeError, match="probe"):
        build_launch_envelope(
            **_kwargs(tmp_path, arm_state=ArmState.PREFLIGHT_PROBE, task_bearing=False,
                      probe_argv=("codex", "exec", "do task"), probe_kind="task")
        )


def test_unresolved_placeholder_and_shell_string_are_rejected(tmp_path):
    with pytest.raises(LaunchEnvelopeError, match="placeholder"):
        build_launch_envelope(**_kwargs(tmp_path, argv_override=("codex", "{missing}")))
    with pytest.raises(LaunchEnvelopeError, match="argv"):
        build_launch_envelope(**_kwargs(tmp_path, argv_override="codex exec --json"))


def test_envelope_hash_and_idempotency_key_are_deterministic(tmp_path):
    first = build_launch_envelope(**_kwargs(tmp_path))
    second = build_launch_envelope(**_kwargs(tmp_path))
    assert first.envelope_sha256 == second.envelope_sha256
    assert first.idempotency_key == second.idempotency_key
    assert len(first.envelope_sha256) == 64
    assert first.cwd == str(tmp_path.resolve())
