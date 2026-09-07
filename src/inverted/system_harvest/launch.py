from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .adapters.base import AcquisitionAdapter, LaunchSpec
from .arming import ALLOWED_PREFLIGHT_PROBES, ArmState
from .schedule import ExecutionCell


class LaunchEnvelopeError(ValueError):
    pass


@dataclass(frozen=True)
class LaunchValidationReport:
    valid: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class LaunchEnvelope:
    campaign_id: str
    cell_id: str
    execution_id: str
    escalation_level: int
    system_id: str
    adapter_id: str
    mode_id: str
    action_kind: str
    arm_state: ArmState
    argv: tuple[str, ...]
    cwd: str
    fixture_sha256: str
    workspace_fixture_id: str
    model_runtime_id: str
    perturbations: tuple[str, ...]
    timeout_seconds: float
    no_progress_seconds: float | None
    permission_policy: str
    source_identity: str
    environment_fingerprints: tuple[tuple[str, str], ...]
    run_dir: str
    idempotency_key: str
    envelope_sha256: str


def _canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _launch_spec(adapter: AcquisitionAdapter, mode_id: str) -> LaunchSpec:
    for spec in adapter.descriptor.launch_specs:
        if spec.mode_id == mode_id:
            return spec
    raise LaunchEnvelopeError(f"adapter has no declared launch mode: {mode_id}")


def _expand(argv: Sequence[str], substitutions: Mapping[str, str]) -> tuple[str, ...]:
    expanded: list[str] = []
    for token in argv:
        value = token
        for key, replacement in substitutions.items():
            value = value.replace("{" + key + "}", str(replacement))
        if re.search(r"\{[^{}]+\}", value):
            raise LaunchEnvelopeError(f"unresolved launch placeholder: {value}")
        expanded.append(value)
    if not expanded or any(not item for item in expanded):
        raise LaunchEnvelopeError("argv must contain non-empty positional arguments")
    return tuple(expanded)


def validate_launch_envelope(envelope: LaunchEnvelope) -> LaunchValidationReport:
    blockers: list[str] = []
    if not envelope.argv:
        blockers.append("argv missing")
    if not Path(envelope.cwd).is_absolute():
        blockers.append("cwd must be absolute")
    if len(envelope.fixture_sha256) != 64:
        blockers.append("fixture hash invalid")
    if envelope.timeout_seconds <= 0:
        blockers.append("timeout must be positive")
    if envelope.no_progress_seconds is not None and envelope.no_progress_seconds <= 0:
        blockers.append("no-progress threshold must be positive")
    if envelope.action_kind == "TASK" and not envelope.arm_state.task_execution_allowed:
        blockers.append("task execution requires ARMED_LIVE")
    if envelope.action_kind == "PREFLIGHT_PROBE" and not envelope.arm_state.probe_execution_allowed:
        blockers.append("preflight probe arm state invalid")
    return LaunchValidationReport(not blockers, tuple(blockers))


def build_launch_envelope(*, campaign_id: str, cell: ExecutionCell, execution_id: str,
                          escalation_level: int, adapter: AcquisitionAdapter,
                          workspace: str | Path, run_dir: str | Path, arm_state: ArmState,
                          substitutions: Mapping[str, str], source_identity: str,
                          environment_fingerprints: Mapping[str, str], timeout_seconds: float,
                          no_progress_seconds: float | None = None,
                          permission_policy: str = "default", task_bearing: bool = True,
                          probe_argv: Sequence[str] | None = None, probe_kind: str | None = None,
                          argv_override: Sequence[str] | str | None = None) -> LaunchEnvelope:
    if escalation_level < 0:
        raise LaunchEnvelopeError("escalation_level must be non-negative")
    workspace_path = Path(workspace)
    run_path = Path(run_dir)
    if not workspace_path.is_absolute() or not run_path.is_absolute():
        raise LaunchEnvelopeError("workspace and run_dir must be absolute")
    if task_bearing and not arm_state.task_execution_allowed:
        raise LaunchEnvelopeError("task-bearing launch requires ARMED_LIVE")

    if task_bearing:
        if isinstance(argv_override, str):
            raise LaunchEnvelopeError("argv must be a positional sequence, not a shell string")
        spec = _launch_spec(adapter, cell.execution_mode)
        argv_source = tuple(argv_override) if argv_override is not None else spec.argv
        values = dict(substitutions)
        values.setdefault("workspace", str(workspace_path))
        values.setdefault("run_dir", str(run_path))
        argv = _expand(argv_source, values)
        action_kind = "TASK"
        mode_id = spec.mode_id
    else:
        if probe_kind not in ALLOWED_PREFLIGHT_PROBES:
            raise LaunchEnvelopeError("preflight probe kind is not allowlisted")
        if not arm_state.probe_execution_allowed:
            raise LaunchEnvelopeError("preflight probe requires PREFLIGHT_PROBE or ARMED_LIVE")
        if probe_argv is None or isinstance(probe_argv, str):
            raise LaunchEnvelopeError("probe argv must be a positional sequence")
        argv = _expand(tuple(probe_argv), {})
        action_kind = "PREFLIGHT_PROBE"
        mode_id = f"probe:{probe_kind}"
    base = {
        "campaign_id": campaign_id, "cell_id": cell.cell_id, "execution_id": execution_id,
        "escalation_level": escalation_level, "system_id": cell.system_id,
        "adapter_id": cell.adapter_id, "mode_id": mode_id, "action_kind": action_kind,
        "arm_state": arm_state.value, "argv": list(argv), "cwd": str(workspace_path),
        "fixture_sha256": cell.fixture_sha256, "workspace_fixture_id": cell.workspace_fixture_id,
        "model_runtime_id": cell.model_runtime_id, "perturbations": list(cell.perturbations),
        "timeout_seconds": float(timeout_seconds), "no_progress_seconds": no_progress_seconds,
        "permission_policy": permission_policy,
        "source_identity": source_identity,
        "environment_fingerprints": sorted((str(k), str(v)) for k, v in environment_fingerprints.items()),
        "run_dir": str(run_path),
    }
    idempotency_key = _canonical_hash({
        "campaign_id": campaign_id, "cell_id": cell.cell_id, "execution_id": execution_id,
        "escalation_level": escalation_level, "argv": list(argv), "cwd": str(workspace_path),
    })
    envelope_sha256 = _canonical_hash({**base, "idempotency_key": idempotency_key})
    envelope = LaunchEnvelope(
        campaign_id, cell.cell_id, execution_id, escalation_level, cell.system_id,
        cell.adapter_id, mode_id, action_kind, arm_state, argv, str(workspace_path),
        cell.fixture_sha256, cell.workspace_fixture_id, cell.model_runtime_id,
        tuple(cell.perturbations), float(timeout_seconds), no_progress_seconds,
        permission_policy, source_identity, tuple(base["environment_fingerprints"]),
        str(run_path), idempotency_key, envelope_sha256,
    )
    report = validate_launch_envelope(envelope)
    if not report.valid:
        raise LaunchEnvelopeError("; ".join(report.blockers))
    return envelope
