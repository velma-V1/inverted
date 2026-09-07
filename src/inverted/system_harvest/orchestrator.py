from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from .acquisition import AcquisitionRecorder
from .adapters.preflight import PreflightReport
from .adapters.registry import adapter_by_id
from .backend import BackendObservation, BackendResult, ExecutionBackend
from .escalation import (
    EscalationCapsule, SnapshotSection, build_escalation_capsule, verify_escalation_capsule,
)
from .execution import AttemptOutcome
from .journal import HarvestJournal
from .schedule import CampaignSchedule, ExecutionCell, append_supplemental_cell


class CellState(str, Enum):
    PLANNED = "PLANNED"
    PREFLIGHT_READY = "PREFLIGHT_READY"
    SNAPSHOT_BEFORE_CAPTURED = "SNAPSHOT_BEFORE_CAPTURED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SNAPSHOT_AFTER_CAPTURED = "SNAPSHOT_AFTER_CAPTURED"
    FAILURE_BOUNDARY_CAPTURE = "FAILURE_BOUNDARY_CAPTURE"
    STALL_BOUNDARY_CAPTURE = "STALL_BOUNDARY_CAPTURE"
    ESCALATION_PENDING = "ESCALATION_PENDING"
    INFRA_INTERRUPTED = "INFRA_INTERRUPTED"
    RECOVERY_UNCERTAIN = "RECOVERY_UNCERTAIN"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class CellRuntimeState:
    cell_id: str
    state: CellState = CellState.PLANNED
    escalation_level: int = 0
    execution_id: str | None = None
    session_handle: str | None = None
    manifest_verified: bool = False
    terminal_status: str | None = None
    parent_capsule_id: str | None = None
    selected_model_id: str | None = None


@dataclass(frozen=True)
class CampaignRuntimeState:
    cells: tuple[CellRuntimeState, ...]

    def by_id(self, cell_id: str) -> CellRuntimeState:
        return next(item for item in self.cells if item.cell_id == cell_id)


@dataclass(frozen=True)
class EscalationRoute:
    eligible_model_ids: tuple[str, ...]
    selected_model_id: str
    reason: str
    capability_tier: str
    runtime_identity: str


class EscalationRouter(Protocol):
    def route(self, cell: ExecutionCell, capsule: EscalationCapsule) -> EscalationRoute:
        ...


class FakeEscalationRouter:
    def __init__(self, routes: dict[int, EscalationRoute]):
        self.routes = dict(routes)
        self.calls: list[tuple[str, str, int]] = []

    def route(self, cell: ExecutionCell, capsule: EscalationCapsule) -> EscalationRoute:
        if capsule.escalation_level not in self.routes:
            raise RuntimeError(f"no escalation route for level {capsule.escalation_level}")
        self.calls.append((cell.cell_id, capsule.capsule_id, capsule.escalation_level))
        return self.routes[capsule.escalation_level]


SnapshotProvider = Callable[[ExecutionCell, BackendResult, str, int], tuple[SnapshotSection, ...]]
VerifierProvider = Callable[[ExecutionCell, BackendResult], dict[str, object]]


class CampaignOrchestrator:
    def __init__(self, schedule: CampaignSchedule, backend: ExecutionBackend,
                 run_root: str | Path, preflight_reports: dict[str, PreflightReport], *,
                 snapshot_provider: SnapshotProvider | None = None,
                 escalation_router: EscalationRouter | None = None,
                 verifier_provider: VerifierProvider | None = None):
        self.schedule = schedule
        self.backend = backend
        self.run_root = Path(run_root)
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.preflight_reports = dict(preflight_reports)
        self.snapshot_provider = snapshot_provider
        self.escalation_router = escalation_router
        self.verifier_provider = verifier_provider
        self.journal = HarvestJournal(self.run_root / "orchestrator.jsonl", schedule.campaign_id)
        self._states = {cell.cell_id: CellRuntimeState(cell.cell_id) for cell in self._all_cells()}
        if not self.journal.read_all():
            self.journal.append("SCHEDULE_FROZEN", {
                "baseline_sha256": schedule.baseline_sha256,
                "baseline_cell_ids": [cell.cell_id for cell in schedule.baseline_cells],
                "supplemental_cell_ids": [item.cell.cell_id for item in schedule.supplemental_cells],
            })
        else:
            self._replay_journal()

    def _all_cells(self) -> tuple[ExecutionCell, ...]:
        return self.schedule.baseline_cells + tuple(item.cell for item in self.schedule.supplemental_cells)

    @property
    def runtime_state(self) -> CampaignRuntimeState:
        return CampaignRuntimeState(tuple(self._states[cell.cell_id] for cell in self._all_cells()))

    def _replay_journal(self) -> None:
        for record in self.journal.read_all():
            payload = record.payload if isinstance(record.payload, dict) else {}
            cell_id = payload.get("cell_id")
            if not cell_id or cell_id not in self._states:
                continue
            current = self._states[cell_id]
            if record.kind == "CELL_STATE_CHANGED":
                self._states[cell_id] = replace(
                    current, state=CellState(payload["to"]),
                    escalation_level=int(payload.get("escalation_level", current.escalation_level)),
                    execution_id=payload.get("execution_id") or current.execution_id,
                )
            elif record.kind == "INFRA_INTERRUPTION_RECORDED":
                self._states[cell_id] = replace(current, session_handle=payload.get("session_handle"))
            elif record.kind == "ESCALATION_ROUTED":
                self._states[cell_id] = replace(current, selected_model_id=payload.get("selected_model_id"))
            elif record.kind == "ESCALATION_CAPSULE_PERSISTED":
                self._states[cell_id] = replace(current, parent_capsule_id=payload.get("capsule_id"))
            elif record.kind == "ARTIFACT_MANIFEST_VERIFIED" and payload.get("complete") is True:
                self._states[cell_id] = replace(current, manifest_verified=True)
            elif record.kind == "CELL_COMPLETED":
                self._states[cell_id] = replace(current, terminal_status=payload.get("terminal_status"))

    def _set_state(self, cell: ExecutionCell, state: CellState, **changes) -> CellRuntimeState:
        current = self._states[cell.cell_id]
        updated = replace(current, state=state, **changes)
        self.journal.append("CELL_STATE_CHANGED", {
            "cell_id": cell.cell_id, "from": current.state.value, "to": state.value,
            "escalation_level": updated.escalation_level, "execution_id": updated.execution_id,
        })
        self._states[cell.cell_id] = updated
        return updated

    def _eligible_cell(self) -> ExecutionCell:
        blocked: list[str] = []
        for cell in self._all_cells():
            state = self._states[cell.cell_id]
            if state.state is CellState.COMPLETE:
                continue
            report = self.preflight_reports.get(cell.adapter_id)
            if report is None or not report.ready:
                blocked.append(cell.cell_id)
                continue
            return cell
        if blocked:
            raise RuntimeError("preflight blocks all remaining cells: " + ", ".join(blocked))
        raise RuntimeError("no incomplete eligible cells remain")

    def _execution_id(self, cell: ExecutionCell, level: int) -> str:
        return f"{self.schedule.campaign_id}:{cell.system_id}:{cell.cell_id}:L{level}"

    def _persist_observation(self, recorder: AcquisitionRecorder,
                             observation: BackendObservation) -> None:
        if observation.kind == "stream":
            if observation.raw_bytes is not None:
                digest = recorder.record_native_bytes(
                    observation.artifact_id, observation.raw_bytes,
                    source_path=observation.source_path, ordinal=observation.ordinal,
                    format=observation.format,
                )
            elif observation.raw_text is not None:
                record = recorder.record_native_text(
                    observation.artifact_id, observation.raw_text,
                    source_path=observation.source_path, ordinal=observation.ordinal,
                    format=observation.format,
                )
                digest = record.raw_sha256
            else:
                raise ValueError("stream observation has no raw payload")
        elif observation.kind == "artifact":
            raw = observation.raw_bytes
            if raw is None:
                if observation.raw_text is None:
                    raise ValueError("artifact observation has no raw payload")
                raw = observation.raw_text.encode("utf-8")
            item = recorder.record_artifact_bytes(
                observation.artifact_id, raw,
                source_path=observation.source_path, format=observation.format,
            )
            digest = item.sha256
        else:
            raise ValueError(f"unknown backend observation kind: {observation.kind}")
        self.journal.append("BACKEND_OBSERVATION_PERSISTED", {
            "cell_id": recorder.task_id, "artifact_id": observation.artifact_id,
            "ordinal": observation.ordinal, "source_path": observation.source_path,
            "sha256": digest,
        })

    def _persist_capsule(self, capsule: EscalationCapsule) -> Path:
        root = self.run_root / "01_RAW" / "escalation-capsules"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{capsule.capsule_id}.json"
        payload = {
            "capsule_id": capsule.capsule_id, "campaign_id": capsule.campaign_id,
            "system_id": capsule.system_id, "example_id": capsule.example_id,
            "escalation_level": capsule.escalation_level, "source_model_id": capsule.source_model_id,
            "failure_event_id": capsule.failure_event_id, "parent_capsule_id": capsule.parent_capsule_id,
            "resume_mode": capsule.resume_mode, "continuation_directive": capsule.continuation_directive,
            "capsule_sha256": capsule.capsule_sha256,
            "sections": [{"name": s.name, "status": s.status.value, "payload": s.payload,
                          "evidence_ids": list(s.evidence_ids), "reason": s.reason} for s in capsule.sections],
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        if path.exists():
            if path.read_bytes() != raw:
                raise RuntimeError("existing escalation capsule content mismatch")
            return path
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def _capture_and_route(self, cell: ExecutionCell, result: BackendResult,
                           boundary_kind: str, failure_event_id: str) -> CellRuntimeState:
        current = self._states[cell.cell_id]
        if self.snapshot_provider is None or self.escalation_router is None:
            raise RuntimeError("escalation requires snapshot_provider and escalation_router")
        next_level = current.escalation_level + 1
        sections = self.snapshot_provider(cell, result, boundary_kind, current.escalation_level)
        source_model = current.selected_model_id or cell.model_runtime_id
        capsule = build_escalation_capsule(
            campaign_id=self.schedule.campaign_id, system_id=cell.system_id,
            example_id=cell.cell_id, escalation_level=next_level,
            source_model_id=source_model, failure_event_id=failure_event_id,
            sections=sections, parent_capsule_id=current.parent_capsule_id,
        )
        if not verify_escalation_capsule(capsule):
            raise RuntimeError("escalation capsule failed integrity verification")
        path = self._persist_capsule(capsule)
        self.journal.append("ESCALATION_CAPSULE_PERSISTED", {
            "cell_id": cell.cell_id, "capsule_id": capsule.capsule_id,
            "capsule_sha256": capsule.capsule_sha256, "path": str(path),
            "parent_capsule_id": capsule.parent_capsule_id,
            "resume_mode": capsule.resume_mode,
        })
        register_capsule = getattr(self.backend, "register_escalation_capsule", None)
        if callable(register_capsule):
            register_capsule(capsule.capsule_id, {
                "capsule_id": capsule.capsule_id,
                "capsule_sha256": capsule.capsule_sha256,
                "resume_mode": capsule.resume_mode,
                "continuation_directive": capsule.continuation_directive,
                "path": str(path),
            })
        route = self.escalation_router.route(cell, capsule)
        self.journal.append("ESCALATION_ROUTED", {
            "cell_id": cell.cell_id, "capsule_id": capsule.capsule_id,
            "eligible_model_ids": list(route.eligible_model_ids),
            "selected_model_id": route.selected_model_id, "reason": route.reason,
            "capability_tier": route.capability_tier, "runtime_identity": route.runtime_identity,
        })
        return self._set_state(
            cell, CellState.ESCALATION_PENDING, escalation_level=next_level,
            execution_id=self._execution_id(cell, next_level),
            parent_capsule_id=capsule.capsule_id, selected_model_id=route.selected_model_id,
        )

    def _begin_baseline(self, cell: ExecutionCell) -> tuple[str, int]:
        current = self._states[cell.cell_id]
        level = current.escalation_level
        execution_id = current.execution_id or self._execution_id(cell, level)
        self.journal.append("CELL_SELECTED", {
            "cell_id": cell.cell_id, "execution_id": execution_id, "escalation_level": level,
        })
        self._set_state(cell, CellState.PREFLIGHT_READY, execution_id=execution_id)
        self.journal.append("CELL_PREFLIGHT_RECORDED", {
            "cell_id": cell.cell_id, "adapter_id": cell.adapter_id, "ready": True,
        })
        self._set_state(cell, CellState.SNAPSHOT_BEFORE_CAPTURED)
        self.journal.append("SNAPSHOT_BEFORE_CAPTURED", {
            "cell_id": cell.cell_id, "fixture_sha256": cell.fixture_sha256,
            "task_contract": cell.task_contract, "instructions": cell.original_instructions,
        })
        self._set_state(cell, CellState.EXECUTING)
        return execution_id, level

    def _begin_escalation_continuation(self, cell: ExecutionCell) -> tuple[str, int]:
        current = self._states[cell.cell_id]
        if not current.execution_id or not current.parent_capsule_id or not current.selected_model_id:
            raise RuntimeError("escalation pending state lacks continuation identity")
        self.journal.append("ESCALATION_CONTINUATION_STARTED", {
            "cell_id": cell.cell_id, "execution_id": current.execution_id,
            "escalation_level": current.escalation_level,
            "capsule_id": current.parent_capsule_id,
            "selected_model_id": current.selected_model_id,
            "resume_mode": "CONTINUE_FROM_FAILURE_BOUNDARY",
        })
        self._set_state(cell, CellState.EXECUTING)
        return current.execution_id, current.escalation_level

    def _backend_run(self, cell: ExecutionCell, execution_id: str, level: int):
        current = self._states[cell.cell_id]
        if current.parent_capsule_id and current.selected_model_id and level > 0:
            method = getattr(self.backend, "continue_from_escalation")
            return method(cell.cell_id, execution_id, level, current.parent_capsule_id, current.selected_model_id)
        return self.backend.execute(cell.cell_id, execution_id, level)

    def run_next_eligible(self) -> CellRuntimeState:
        cell = self._eligible_cell()
        current = self._states[cell.cell_id]
        resume_session: str | None = None
        if current.state is CellState.INFRA_INTERRUPTED:
            if not current.session_handle:
                self.journal.append("RECOVERY_RECONCILIATION_UNCERTAIN", {
                    "cell_id": cell.cell_id, "execution_id": current.execution_id,
                    "reason": "infrastructure interruption has no resumable session handle",
                })
                return self._set_state(cell, CellState.RECOVERY_UNCERTAIN)
            if not current.execution_id:
                raise RuntimeError("interrupted cell lacks execution_id")
            execution_id, level = current.execution_id, current.escalation_level
            resume_session = current.session_handle
            self.journal.append("INFRA_RESUME_STARTED", {
                "cell_id": cell.cell_id, "execution_id": execution_id,
                "escalation_level": level, "session_handle": resume_session,
            })
            self._set_state(cell, CellState.EXECUTING)
        elif current.state is CellState.ESCALATION_PENDING:
            execution_id, level = self._begin_escalation_continuation(cell)
        else:
            execution_id, level = self._begin_baseline(cell)

        adapter = adapter_by_id(cell.adapter_id)
        recorder = AcquisitionRecorder(
            self.schedule.campaign_id, execution_id, cell.cell_id, adapter,
            self.run_root / "cells" / cell.cell_id / f"L{level}", self.preflight_reports[cell.adapter_id],
        )
        if resume_session is not None:
            observations, result = self.backend.resume(cell.cell_id, execution_id, level, resume_session)
        else:
            observations, result = self._backend_run(cell, execution_id, level)
        for observation in observations:
            self._persist_observation(recorder, observation)
        self._states[cell.cell_id] = replace(self._states[cell.cell_id], session_handle=result.session_handle)

        if result.outcome is AttemptOutcome.INFRA_INTERRUPTION:
            self.journal.append("INFRA_INTERRUPTION_RECORDED", {
                "cell_id": cell.cell_id, "execution_id": execution_id,
                "session_handle": result.session_handle,
            })
            return self._set_state(cell, CellState.INFRA_INTERRUPTED)

        if result.outcome is AttemptOutcome.STALL:
            stall_record = self.journal.append("STALL_VERDICT_RECORDED", {
                "cell_id": cell.cell_id, "execution_id": execution_id,
                "detector": result.verifier_payload.get("stall_detector", {}),
            })
            self._set_state(cell, CellState.STALL_BOUNDARY_CAPTURE)
            return self._capture_and_route(cell, result, "STALL", stall_record.record_sha256)

        self._set_state(cell, CellState.VERIFYING)
        verifier_payload = (
            self.verifier_provider(cell, result)
            if self.verifier_provider is not None
            else result.verifier_payload
        )
        verdict = str(verifier_payload.get("verdict", "INDETERMINATE"))
        verifier_record = self.journal.append("VERIFIER_RECORDED", {
            "cell_id": cell.cell_id, "execution_id": execution_id,
            "verdict": verdict, "payload": verifier_payload,
        })
        if result.outcome is AttemptOutcome.INCORRECT or verdict == "INCORRECT":
            self._set_state(cell, CellState.FAILURE_BOUNDARY_CAPTURE)
            return self._capture_and_route(cell, result, "INCORRECT", verifier_record.record_sha256)
        if verdict != "PASS":
            return self._states[cell.cell_id]

        self._set_state(cell, CellState.SNAPSHOT_AFTER_CAPTURED)
        self.journal.append("SNAPSHOT_AFTER_CAPTURED", {
            "cell_id": cell.cell_id, "execution_id": execution_id,
            "session_handle": result.session_handle,
        })
        _, manifest_report = recorder.finalize_manifest()
        self.journal.append("ARTIFACT_MANIFEST_VERIFIED", {
            "cell_id": cell.cell_id, "complete": manifest_report.complete,
            "blockers": list(manifest_report.blockers),
        })
        if not manifest_report.complete:
            return self._states[cell.cell_id]
        self._states[cell.cell_id] = replace(self._states[cell.cell_id], manifest_verified=True)
        terminal = "PASS" if level == 0 else "RECOVERED_BY_ESCALATION"
        self.journal.append("CELL_COMPLETED", {
            "cell_id": cell.cell_id, "execution_id": execution_id,
            "terminal_status": terminal,
        })
        return self._set_state(cell, CellState.COMPLETE, terminal_status=terminal)


    def admit_supplemental(self, cell: ExecutionCell, *, origin_evidence_ids: tuple[str, ...],
                           discovery: str, decision_value: str,
                           closure_condition: str) -> CampaignSchedule:
        updated = append_supplemental_cell(
            self.schedule, cell, origin_evidence_ids=origin_evidence_ids,
            discovery=discovery, decision_value=decision_value,
            closure_condition=closure_condition,
        )
        self.journal.append("SUPPLEMENTAL_CELL_ADMITTED", {
            "cell_id": cell.cell_id, "origin_evidence_ids": list(origin_evidence_ids),
            "discovery": discovery, "decision_value": decision_value,
            "closure_condition": closure_condition,
            "baseline_sha256": self.schedule.baseline_sha256,
        })
        self.schedule = updated
        self._states[cell.cell_id] = CellRuntimeState(cell.cell_id)
        return updated


@dataclass(frozen=True)
class CompletionGates:
    future_query_ready: bool
    cross_system_manifest_verified: bool
    system_reports_verified: bool
    evidence_coverage_verified: bool


@dataclass(frozen=True)
class OrchestratorCompletionReport:
    complete: bool
    blockers: tuple[str, ...]


def evaluate_orchestrator_completion(orchestrator: CampaignOrchestrator,
                                     gates: CompletionGates) -> OrchestratorCompletionReport:
    blockers: list[str] = []
    for cell in orchestrator._all_cells():
        state = orchestrator._states[cell.cell_id]
        if state.state is not CellState.COMPLETE:
            blockers.append(f"cell not complete: {cell.cell_id} ({state.state.value})")
            continue
        if not state.manifest_verified:
            blockers.append(f"artifact manifest not verified: {cell.cell_id}")
        if state.terminal_status == "RECOVERED_BY_ESCALATION" and not state.parent_capsule_id:
            blockers.append(f"escalation chain not verified: {cell.cell_id}")
    if not gates.future_query_ready:
        blockers.append("future query gate not ready")
    if not gates.cross_system_manifest_verified:
        blockers.append("cross-system manifest not verified")
    if not gates.system_reports_verified:
        blockers.append("system completion reports not verified")
    if not gates.evidence_coverage_verified:
        blockers.append("required evidence-channel coverage not verified")
    return OrchestratorCompletionReport(not blockers, tuple(blockers))
