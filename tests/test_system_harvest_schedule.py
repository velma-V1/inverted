from pathlib import Path

import pytest

from inverted.system_harvest.schedule import (
    ApplicabilityRecord,
    ExecutionCell,
    ScheduleValidationError,
    VerificationContract,
    append_supplemental_cell,
    compile_schedule,
)
from inverted.system_harvest.template import load_harvest_template


TEMPLATE = load_harvest_template(Path("configs/system-harvest-11/campaign.json"))


def _verifier():
    return VerificationContract("verify-exit", "DETERMINISTIC", ("exit_code=0",))


def _cell(system: str, behavior: str, *, perturbations=()):
    return ExecutionCell.create(
        system_id=system, adapter_id="adapter", behavioral_case=behavior,
        perturbations=tuple(perturbations), workspace_fixture_id="fx",
        fixture_sha256="a" * 64, task_contract="task", original_instructions="instructions",
        active_ingredients=("base",), execution_mode="fake", model_runtime_id="model",
        verification=_verifier(), seed_id="seed-1", required_artifact_ids=("artifact",),
        required_evidence_channels=TEMPLATE.required_evidence_channels,
        escalation_route_id="route-1",
    )

def _full_coverage_cells():
    return tuple(_cell(system, behavior) for system in TEMPLATE.systems for behavior in TEMPLATE.behavioral_battery)


def _perturbation_records():
    return tuple(
        ApplicabilityRecord(
            system_id=system, dimension="PERTURBATION", item_id=perturbation,
            status="NOT_APPLICABLE", reason="fixture contract marks this perturbation unavailable",
            evidence_ids=(f"ev-{system}-{perturbation}",),
        )
        for system in TEMPLATE.systems for perturbation in TEMPLATE.perturbation_battery
    )


def test_execution_cell_id_is_stable_and_content_derived():
    a = _cell(TEMPLATE.systems[0], TEMPLATE.behavioral_battery[0])
    b = _cell(TEMPLATE.systems[0], TEMPLATE.behavioral_battery[0])
    assert a.cell_id == b.cell_id
    assert a.cell_id.startswith("CELL-")


def test_compile_schedule_requires_complete_behavior_and_perturbation_accounting():
    schedule = compile_schedule(TEMPLATE, _full_coverage_cells(), _perturbation_records())
    assert len(schedule.baseline_cells) == 11 * 32
    assert schedule.baseline_sha256
    assert schedule.supplemental_cells == ()

def test_compile_schedule_rejects_missing_behavior_pair():
    cells = _full_coverage_cells()[1:]
    with pytest.raises(ScheduleValidationError, match="behavior applicability gap"):
        compile_schedule(TEMPLATE, cells, _perturbation_records())


def test_compile_schedule_rejects_duplicate_cell_and_unhashed_fixture():
    cells = list(_full_coverage_cells())
    cells.append(cells[0])
    with pytest.raises(ScheduleValidationError, match="duplicate cell_id"):
        compile_schedule(TEMPLATE, tuple(cells), _perturbation_records())
    with pytest.raises(ScheduleValidationError, match="fixture_sha256"):
        ExecutionCell.create(
            system_id=TEMPLATE.systems[0], adapter_id="a", behavioral_case=TEMPLATE.behavioral_battery[0],
            perturbations=(), workspace_fixture_id="fx", fixture_sha256="", task_contract="t",
            original_instructions="i", active_ingredients=(), execution_mode="fake",
            model_runtime_id="m", verification=_verifier(), seed_id="s",
            required_artifact_ids=("x",), required_evidence_channels=TEMPLATE.required_evidence_channels,
            escalation_route_id="r",
        )


def test_supplemental_append_preserves_baseline_hash_and_requires_provenance():
    schedule = compile_schedule(TEMPLATE, _full_coverage_cells(), _perturbation_records())
    supplemental = _cell(TEMPLATE.systems[0], TEMPLATE.behavioral_battery[-1], perturbations=(TEMPLATE.perturbation_battery[-1],))
    updated = append_supplemental_cell(
        schedule, supplemental, origin_evidence_ids=("ev-surprise",),
        discovery="new failure mode", decision_value="changes recovery design",
        closure_condition="reproduce and explain boundary",
    )
    assert updated.baseline_sha256 == schedule.baseline_sha256
    assert updated.baseline_cells == schedule.baseline_cells
    assert len(updated.supplemental_cells) == 1
    with pytest.raises(ScheduleValidationError, match="origin_evidence_ids"):
        append_supplemental_cell(schedule, supplemental, origin_evidence_ids=(), discovery="x", decision_value="y", closure_condition="z")
