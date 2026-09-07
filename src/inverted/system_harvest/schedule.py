from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from .types import HarvestTemplate


class ScheduleValidationError(ValueError):
    pass


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class VerificationContract:
    verifier_id: str
    authority: str
    checks: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.verifier_id.strip() or not self.authority.strip() or not self.checks:
            raise ScheduleValidationError("verification contract must be complete")


@dataclass(frozen=True)
class ExecutionCell:
    cell_id: str
    system_id: str
    adapter_id: str
    behavioral_case: str
    perturbations: tuple[str, ...]
    workspace_fixture_id: str
    fixture_sha256: str
    task_contract: str
    original_instructions: str
    active_ingredients: tuple[str, ...]
    execution_mode: str
    model_runtime_id: str
    verification: VerificationContract
    seed_id: str
    required_artifact_ids: tuple[str, ...]
    required_evidence_channels: tuple[str, ...]
    escalation_route_id: str

    @classmethod
    def create(cls, *, system_id: str, adapter_id: str, behavioral_case: str,
               perturbations: tuple[str, ...], workspace_fixture_id: str,
               fixture_sha256: str, task_contract: str, original_instructions: str,
               active_ingredients: tuple[str, ...], execution_mode: str,
               model_runtime_id: str, verification: VerificationContract,
               seed_id: str, required_artifact_ids: tuple[str, ...],
               required_evidence_channels: tuple[str, ...], escalation_route_id: str) -> "ExecutionCell":
        if len(fixture_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in fixture_sha256):
            raise ScheduleValidationError("fixture_sha256 must be a 64-character hex SHA-256")
        values = (system_id, adapter_id, behavioral_case, workspace_fixture_id, task_contract,
                  original_instructions, execution_mode, model_runtime_id, seed_id, escalation_route_id)
        if any(not value.strip() for value in values):
            raise ScheduleValidationError("execution cell required string fields must be non-empty")
        body = {
            "system_id": system_id, "adapter_id": adapter_id, "behavioral_case": behavioral_case,
            "perturbations": list(perturbations), "workspace_fixture_id": workspace_fixture_id,
            "fixture_sha256": fixture_sha256.lower(), "task_contract": task_contract,
            "original_instructions": original_instructions, "active_ingredients": list(active_ingredients),
            "execution_mode": execution_mode, "model_runtime_id": model_runtime_id,
            "verification": asdict(verification), "seed_id": seed_id,
            "required_artifact_ids": list(required_artifact_ids),
            "required_evidence_channels": list(required_evidence_channels),
            "escalation_route_id": escalation_route_id,
        }
        return cls(
            f"CELL-{_hash(body)[:24]}", system_id, adapter_id, behavioral_case,
            tuple(perturbations), workspace_fixture_id, fixture_sha256.lower(), task_contract,
            original_instructions, tuple(active_ingredients), execution_mode, model_runtime_id,
            verification, seed_id, tuple(required_artifact_ids), tuple(required_evidence_channels),
            escalation_route_id,
        )


@dataclass(frozen=True)
class ApplicabilityRecord:
    system_id: str
    dimension: str
    item_id: str
    status: str
    reason: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.dimension not in {"BEHAVIOR", "PERTURBATION"}:
            raise ScheduleValidationError("applicability dimension must be BEHAVIOR or PERTURBATION")
        if self.status not in {"NOT_APPLICABLE", "INACCESSIBLE"}:
            raise ScheduleValidationError("applicability status must be NOT_APPLICABLE or INACCESSIBLE")
        if not self.reason.strip() or not self.evidence_ids:
            raise ScheduleValidationError("applicability record requires reason and evidence_ids")


@dataclass(frozen=True)
class SupplementalCell:
    cell: ExecutionCell
    origin_evidence_ids: tuple[str, ...]
    discovery: str
    decision_value: str
    closure_condition: str


@dataclass(frozen=True)
class CampaignSchedule:
    campaign_id: str
    baseline_cells: tuple[ExecutionCell, ...]
    applicability_records: tuple[ApplicabilityRecord, ...]
    baseline_sha256: str
    supplemental_cells: tuple[SupplementalCell, ...] = ()


def _validate_cell(template: HarvestTemplate, cell: ExecutionCell) -> None:
    if cell.system_id not in template.systems:
        raise ScheduleValidationError(f"unknown system: {cell.system_id}")
    if cell.behavioral_case not in template.behavioral_battery:
        raise ScheduleValidationError(f"unknown behavioral case: {cell.behavioral_case}")
    unknown = sorted(set(cell.perturbations) - set(template.perturbation_battery))
    if unknown:
        raise ScheduleValidationError("unknown perturbation(s): " + ", ".join(unknown))
    if not cell.required_artifact_ids:
        raise ScheduleValidationError("required_artifact_ids must be non-empty")
    if not cell.required_evidence_channels:
        raise ScheduleValidationError("required_evidence_channels must be non-empty")


def compile_schedule(template: HarvestTemplate, cells: tuple[ExecutionCell, ...],
                     applicability_records: tuple[ApplicabilityRecord, ...]) -> CampaignSchedule:
    if not cells:
        raise ScheduleValidationError("baseline cells must be non-empty")
    for cell in cells:
        _validate_cell(template, cell)
    ids = [cell.cell_id for cell in cells]
    if len(ids) != len(set(ids)):
        raise ScheduleValidationError("duplicate cell_id")

    records = {(r.system_id, r.dimension, r.item_id): r for r in applicability_records}
    if len(records) != len(applicability_records):
        raise ScheduleValidationError("duplicate applicability record")
    for record in applicability_records:
        if record.system_id not in template.systems:
            raise ScheduleValidationError(f"unknown applicability system: {record.system_id}")

    behavior_pairs = {(cell.system_id, cell.behavioral_case) for cell in cells}
    for system in template.systems:
        for behavior in template.behavioral_battery:
            if (system, behavior) not in behavior_pairs and (system, "BEHAVIOR", behavior) not in records:
                raise ScheduleValidationError(f"behavior applicability gap: {system} / {behavior}")

    perturb_pairs = {(cell.system_id, p) for cell in cells for p in cell.perturbations}
    for system in template.systems:
        for perturbation in template.perturbation_battery:
            if (system, perturbation) not in perturb_pairs and (system, "PERTURBATION", perturbation) not in records:
                raise ScheduleValidationError(f"perturbation applicability gap: {system} / {perturbation}")

    baseline_body = {
        "campaign_id": template.campaign_id,
        "cells": [asdict(cell) for cell in cells],
        "applicability_records": [asdict(record) for record in applicability_records],
    }
    return CampaignSchedule(
        template.campaign_id, tuple(cells), tuple(applicability_records), _hash(baseline_body), ()
    )


def append_supplemental_cell(schedule: CampaignSchedule, cell: ExecutionCell, *,
                             origin_evidence_ids: tuple[str, ...], discovery: str,
                             decision_value: str, closure_condition: str) -> CampaignSchedule:
    if not origin_evidence_ids:
        raise ScheduleValidationError("origin_evidence_ids must be non-empty")
    if any(not value.strip() for value in (discovery, decision_value, closure_condition)):
        raise ScheduleValidationError("supplemental provenance fields must be non-empty")
    if cell.cell_id in {c.cell_id for c in schedule.baseline_cells}:
        raise ScheduleValidationError("supplemental cell duplicates baseline cell_id")
    if cell.cell_id in {s.cell.cell_id for s in schedule.supplemental_cells}:
        raise ScheduleValidationError("duplicate supplemental cell_id")
    supplemental = SupplementalCell(cell, tuple(origin_evidence_ids), discovery, decision_value, closure_condition)
    return replace(schedule, supplemental_cells=schedule.supplemental_cells + (supplemental,))
