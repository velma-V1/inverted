from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

from .adapters.registry import adapter_by_id
from .arming import ArmState
from .backend import BackendObservation, BackendResult
from .drivers.registry import driver_by_adapter_id
from .environment import EnvironmentPolicy
from .execution import AttemptOutcome
from .launch import LaunchEnvelope, build_launch_envelope
from .process_engine import ProcessEngine, ProcessResult, ProcessTermination
from .schedule import CampaignSchedule, ExecutionCell
from .workspace import WorkspaceLease, WorkspaceLeaseManager


class DuplicateLaunchError(RuntimeError):
    pass


class ProductionBackendError(RuntimeError):
    pass
class _LaunchLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._claimed: set[str] = set()
        self._execution_ids: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("kind") == "CLAIM":
                    self._claimed.add(str(row["idempotency_key"]))
                    self._execution_ids.add(str(row["execution_id"]))

    def assert_execution_unclaimed(self, execution_id: str) -> None:
        if execution_id in self._execution_ids:
            raise DuplicateLaunchError(f"idempotency execution already claimed: {execution_id}")

    def claim(self, envelope: LaunchEnvelope) -> None:
        key = envelope.idempotency_key
        if key in self._claimed:
            raise DuplicateLaunchError(f"idempotency key already claimed: {key}")
        row = {
            "kind": "CLAIM", "idempotency_key": key,
            "envelope_sha256": envelope.envelope_sha256,
            "execution_id": envelope.execution_id,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._claimed.add(key)
        self._execution_ids.add(envelope.execution_id)
class ProductionExecutionBackend:
    def __init__(self, *, schedule: CampaignSchedule,
                 fixture_paths: Mapping[str, str | Path], run_root: str | Path,
                 arm_state: ArmState, environment: Mapping[str, str],
                 environment_policy: EnvironmentPolicy,
                 source_identities: Mapping[str, str],
                 process_engine: ProcessEngine | None = None,
                 synthetic_launch_overrides: Mapping[str, Sequence[str]] | None = None,
                 timeout_seconds: float = 120.0,
                 no_progress_seconds: float | None = None):
        self.schedule = schedule
        self.fixture_paths = {key: Path(value).resolve() for key, value in fixture_paths.items()}
        self.run_root = Path(run_root).resolve()
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.arm_state = arm_state
        self.environment = {str(k): str(v) for k, v in environment.items()}
        self.environment_policy = environment_policy
        self.source_identities = dict(source_identities)
        self.process_engine = process_engine or ProcessEngine()
        self.synthetic_launch_overrides = {
            key: tuple(value) for key, value in (synthetic_launch_overrides or {}).items()
        }
        self.timeout_seconds = float(timeout_seconds)
        self.no_progress_seconds = no_progress_seconds
        self.workspace_manager = WorkspaceLeaseManager(self.run_root / "workspaces")
        self.ledger = _LaunchLedger(self.run_root / "launch-ledger.jsonl")
        self._active_leases: dict[str, WorkspaceLease] = {}
        self._capsules: dict[str, dict[str, object]] = {}
    def _cell(self, cell_id: str) -> ExecutionCell:
        for cell in self.schedule.baseline_cells:
            if cell.cell_id == cell_id:
                return cell
        for item in self.schedule.supplemental_cells:
            if item.cell.cell_id == cell_id:
                return item.cell
        raise KeyError(cell_id)

    def _lease_for(self, cell: ExecutionCell, execution_id: str) -> WorkspaceLease:
        existing = self._active_leases.get(cell.cell_id)
        if existing is not None:
            return existing
        try:
            fixture = self.fixture_paths[cell.workspace_fixture_id]
        except KeyError as exc:
            raise ProductionBackendError(
                f"fixture path missing: {cell.workspace_fixture_id}"
            ) from exc
        lease = self.workspace_manager.acquire(
            cell.cell_id, execution_id, fixture, cell.fixture_sha256,
        )
        self._active_leases[cell.cell_id] = lease
        return lease

    def _source_identity(self, adapter_id: str) -> str:
        value = self.source_identities.get(adapter_id, "")
        if not value.strip():
            raise ProductionBackendError(f"source identity missing: {adapter_id}")
        return value
    def _build_envelope(self, cell: ExecutionCell, execution_id: str,
                        escalation_level: int, lease: WorkspaceLease,
                        *, selected_model_id: str | None = None) -> LaunchEnvelope:
        adapter = adapter_by_id(cell.adapter_id)
        driver = driver_by_adapter_id(cell.adapter_id)
        driver.declared_launch_spec(adapter)
        runtime_cell = replace(cell, model_runtime_id=selected_model_id) if selected_model_id else cell
        snapshot = self.environment_policy.snapshot(self.environment)
        override = self.synthetic_launch_overrides.get(cell.adapter_id)
        substitutions = {
            "task": runtime_cell.original_instructions,
            "workspace": lease.workspace_path,
            "run_dir": str(self.run_root / "executions" / execution_id.replace(":", "_")),
        }
        return build_launch_envelope(
            campaign_id=self.schedule.campaign_id, cell=runtime_cell,
            execution_id=execution_id, escalation_level=escalation_level,
            adapter=adapter, workspace=lease.workspace_path,
            run_dir=Path(substitutions["run_dir"]).resolve(), arm_state=self.arm_state,
            substitutions=substitutions, source_identity=self._source_identity(cell.adapter_id),
            environment_fingerprints=snapshot.fingerprints,
            timeout_seconds=self.timeout_seconds,
            no_progress_seconds=self.no_progress_seconds,
            permission_policy="system-harvest-production",
            argv_override=override,
        )

    @staticmethod
    def _stdin_bytes(cell: ExecutionCell) -> bytes:
        adapter = adapter_by_id(cell.adapter_id)
        for spec in adapter.descriptor.launch_specs:
            if spec.mode_id == cell.execution_mode:
                uses_task_placeholder = any("{task}" in token for token in spec.argv)
                if "-" in spec.argv and not uses_task_placeholder:
                    return (cell.original_instructions + "\n").encode("utf-8")
                break
        return b""
    @staticmethod
    def _outcome(result: ProcessResult) -> AttemptOutcome:
        if result.termination is ProcessTermination.NO_PROGRESS:
            return AttemptOutcome.STALL
        if result.termination in {
            ProcessTermination.TIMEOUT,
            ProcessTermination.CANCELLED,
            ProcessTermination.INFRA_INTERRUPTED,
        }:
            return AttemptOutcome.INFRA_INTERRUPTION
        return AttemptOutcome.COMPLETED

    @staticmethod
    def _artifact_id(cell: ExecutionCell, source: str) -> str:
        if source == "stdout" and cell.required_artifact_ids:
            return cell.required_artifact_ids[0]
        adapter = adapter_by_id(cell.adapter_id)
        if source == "stderr":
            for artifact in adapter.descriptor.native_artifacts:
                if "stderr" in artifact.artifact_id.lower():
                    return artifact.artifact_id
        return f"{cell.adapter_id}.process_{source}"

    def _observations(self, cell: ExecutionCell,
                      result: ProcessResult) -> tuple[BackendObservation, ...]:
        items: list[BackendObservation] = []
        for item in result.observations:
            items.append(BackendObservation(
                kind="stream", artifact_id=self._artifact_id(cell, item.source),
                raw_text=None, raw_bytes=item.persisted_bytes,
                source_path=f"process:{item.source}", ordinal=item.global_ordinal,
                format="binary",
            ))
        return tuple(items)
    def _artifact_observations(self, cell: ExecutionCell, envelope: LaunchEnvelope,
                               process_result: ProcessResult) -> tuple[BackendObservation, ...]:
        root = Path(envelope.run_dir)
        driver = driver_by_adapter_id(cell.adapter_id)
        adapter = adapter_by_id(cell.adapter_id)
        formats = {item.artifact_id: item.format for item in adapter.descriptor.native_artifacts}
        matched: set[Path] = set()
        items: list[BackendObservation] = []
        ordinal = len(process_result.observations)

        for artifact_id, pattern in driver.descriptor.artifact_watch_patterns:
            for candidate in sorted(root.glob(pattern)):
                paths = [candidate] if candidate.is_file() else sorted(
                    item for item in candidate.rglob("*") if item.is_file()
                )
                for path in paths:
                    resolved = path.resolve()
                    if resolved in matched:
                        continue
                    matched.add(resolved)
                    items.append(BackendObservation(
                        kind="artifact", artifact_id=artifact_id, raw_text=None,
                        raw_bytes=path.read_bytes(), source_path=str(path),
                        ordinal=ordinal, format=formats.get(artifact_id, "binary"),
                    ))
                    ordinal += 1

        process_paths = {
            Path(process_result.stdout_capture_path).resolve(),
            Path(process_result.stderr_capture_path).resolve(),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            resolved = path.resolve()
            if resolved in matched or resolved in process_paths:
                continue
            relative = path.relative_to(root).as_posix()
            items.append(BackendObservation(
                kind="artifact", artifact_id=f"discovered:{relative}", raw_text=None,
                raw_bytes=path.read_bytes(), source_path=str(path), ordinal=ordinal,
                format="binary",
            ))
            ordinal += 1
        return tuple(items)

    def _run(self, cell: ExecutionCell, execution_id: str, escalation_level: int,
             *, selected_model_id: str | None = None,
             capsule_id: str | None = None) -> tuple[tuple[BackendObservation, ...], BackendResult]:
        self.ledger.assert_execution_unclaimed(execution_id)
        lease = self._lease_for(cell, execution_id)
        envelope = self._build_envelope(
            cell, execution_id, escalation_level, lease,
            selected_model_id=selected_model_id,
        )
        self.ledger.claim(envelope)
        result = self.process_engine.run(
            envelope, environment=self.environment,
            stdin_bytes=self._stdin_bytes(cell),
            environment_policy=self.environment_policy,
        )
        payload = {
            "semantic_verdict": result.semantic_verdict,
            "process_termination": result.termination.value,
            "process_exit_code": result.exit_code,
            "process_pid": result.pid,
            "capture_opened_before_stdin": result.capture_opened_before_stdin,
            "workspace_lease_id": lease.lease_id,
        }
        if result.termination is ProcessTermination.NO_PROGRESS:
            payload["stall_detector"] = {
                "kind": "NO_PROGRESS", "threshold_seconds": self.no_progress_seconds,
            }
        if capsule_id is not None:
            payload.update({
                "resume_mode": "CONTINUE_FROM_FAILURE_BOUNDARY",
                "capsule_id": capsule_id,
                "selected_model_id": selected_model_id,
            })
        observations = self._observations(cell, result) + self._artifact_observations(cell, envelope, result)
        return observations, BackendResult(
            self._outcome(result), None, payload,
        )

    def execute(self, cell_id: str, execution_id: str, escalation_level: int):
        return self._run(self._cell(cell_id), execution_id, escalation_level)
    def resume(self, cell_id: str, execution_id: str, escalation_level: int,
               session_handle: str):
        cell = self._cell(cell_id)
        lease = self._active_leases.get(cell_id)
        if lease is not None:
            self.workspace_manager.mark_recovery_uncertain(lease.lease_id)
        return (), BackendResult(
            AttemptOutcome.INFRA_INTERRUPTION, session_handle,
            {
                "semantic_verdict": None,
                "recovery_uncertain": True,
                "reason": "native session reconciliation is not yet proven; blind resend forbidden",
            },
        )

    def register_escalation_capsule(self, capsule_id: str,
                                    payload: Mapping[str, object]) -> None:
        if not capsule_id.strip():
            raise ValueError("capsule_id must be non-empty")
        self._capsules[capsule_id] = dict(payload)

    def continue_from_escalation(self, cell_id: str, execution_id: str,
                                 escalation_level: int, capsule_id: str,
                                 selected_model_id: str):
        if capsule_id not in self._capsules:
            raise KeyError(capsule_id)
        if not selected_model_id.strip():
            raise ValueError("selected_model_id must be non-empty")
        return self._run(
            self._cell(cell_id), execution_id, escalation_level,
            selected_model_id=selected_model_id, capsule_id=capsule_id,
        )
