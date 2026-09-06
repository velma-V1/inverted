"""Descriptive, recipe-neutral analysis for the Stage 2A-0 calibration."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from numbers import Real
from typing import Any, Iterable, Mapping

from .cases import OPERATING_REGIONS
from .stages import build_canonical_a0_plan


CellKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class CellNoise:
    successes: int
    failures: int
    correctness_instability: float
    answer_instability: float
    eligible: bool


@dataclass(frozen=True)
class ModelNoise:
    correctness_noise_floor: float
    answer_noise_floor: float
    eligible_cell_count: int


@dataclass(frozen=True)
class NoiseCalibration:
    cells: Mapping[CellKey, CellNoise]
    by_model: Mapping[str, ModelNoise]
    correctness_noise_floor: float
    answer_noise_floor: float


@dataclass(frozen=True)
class PairedEffect:
    matched_n: int
    left_only_wins: int
    right_only_wins: int
    ties: int
    net_wins: int
    rate_delta: float


@dataclass(frozen=True)
class A0ModelSummary:
    correctness: Mapping[str, tuple[int, int]]
    correctness_noise_floor: float
    answer_noise_floor: float
    paired_effect: PairedEffect
    paired_effect_by_region: Mapping[str, PairedEffect]
    region_flags: Mapping[str, "RegionFlags"]
    model_role: str
    eligible_for_recipe: bool
    saturation_flag: bool
    ceiling_flag: bool
    runtime_seconds: tuple[float, ...]
    load_seconds: tuple[float, ...]
    prompt_eval_seconds: tuple[float, ...]
    eval_seconds: tuple[float, ...]


@dataclass(frozen=True)
class A0Summary:
    models: Mapping[str, A0ModelSummary]
    noise: NoiseCalibration
    promoted_recipe: None = None


@dataclass(frozen=True)
class RegionFlags:
    raw_ceiling: bool
    historical_ceiling: bool
    saturated: bool


def _get(row: object, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(row, Mapping) and name in row:
            return row[name]
        if hasattr(row, name):
            return getattr(row, name)
    return default


def _has(row: object, name: str) -> bool:
    return (isinstance(row, Mapping) and name in row) or hasattr(row, name)


def _cell_key(row: object) -> CellKey:
    return (
        str(_get(row, "model_key", "model")),
        str(_get(row, "case_id")),
        str(_get(row, "operating_region", "region")),
        str(_get(row, "treatment_kind", "treatment_id", "treatment")),
    )


def calibrate_noise(rows: Iterable[object]) -> NoiseCalibration:
    grouped: dict[CellKey, list[object]] = defaultdict(list)
    for row in rows:
        grouped[_cell_key(row)].append(row)
    cells: dict[CellKey, CellNoise] = {}
    eligible_by_model: dict[str, list[CellNoise]] = defaultdict(list)
    for key, cell_rows in grouped.items():
        successes = sum(bool(_get(row, "correct", "success", default=False)) for row in cell_rows)
        failures = len(cell_rows) - successes
        answers = Counter(str(_get(row, "normalized_answer", "answer", default="")) for row in cell_rows)
        replicates = {_get(row, "replicate") for row in cell_rows}
        eligible = len(cell_rows) == 4 and replicates == {1, 2, 3, 4}
        cell = CellNoise(
            successes=successes,
            failures=failures,
            correctness_instability=min(successes, failures) / 4 if eligible else 0.0,
            answer_instability=1.0 - max(answers.values(), default=0) / 4 if eligible else 0.0,
            eligible=eligible,
        )
        cells[key] = cell
        if eligible:
            eligible_by_model[key[0]].append(cell)
    by_model = {
        model: ModelNoise(
            correctness_noise_floor=max((cell.correctness_instability for cell in eligible), default=0.0),
            answer_noise_floor=max((cell.answer_instability for cell in eligible), default=0.0),
            eligible_cell_count=len(eligible),
        )
        for model, eligible in eligible_by_model.items()
    }
    return NoiseCalibration(
        cells=cells,
        by_model=by_model,
        correctness_noise_floor=max((value.correctness_noise_floor for value in by_model.values()), default=0.0),
        answer_noise_floor=max((value.answer_noise_floor for value in by_model.values()), default=0.0),
    )


def paired_effect(rows: Iterable[object], left: str = "RAW", right: str = "HISTORICAL_SEED") -> PairedEffect:
    pairs: dict[tuple[str, str, str, int], dict[str, bool]] = defaultdict(dict)
    for row in rows:
        treatment = str(_get(row, "treatment_kind", "treatment_id", "treatment"))
        if treatment in {left, right}:
            pairs[(str(_get(row, "model_key", "model")), str(_get(row, "case_id")), str(_get(row, "operating_region", "region")), int(_get(row, "replicate")))][treatment] = bool(_get(row, "correct", "success", default=False))
    matched = [pair for pair in pairs.values() if left in pair and right in pair]
    left_only = sum(pair[left] and not pair[right] for pair in matched)
    right_only = sum(pair[right] and not pair[left] for pair in matched)
    ties = len(matched) - left_only - right_only
    left_rate = sum(pair[left] for pair in matched) / len(matched) if matched else 0.0
    right_rate = sum(pair[right] for pair in matched) / len(matched) if matched else 0.0
    return PairedEffect(len(matched), left_only, right_only, ties, right_only - left_only, right_rate - left_rate)


def _distribution(rows: Iterable[object], *names: str) -> tuple[float, ...]:
    values = (_get(row, *names) for row in rows)
    return tuple(sorted(float(value) for value in values if value is not None))


def _validate_a0_evidence(rows: tuple[object, ...]) -> None:
    plan = build_canonical_a0_plan()
    canonical = {unit.unit_id: unit for unit in plan.units}
    schedule_fields = tuple(vars(plan.units[0]))
    result_fields = (
        "correct", "normalized_answer", "runtime_seconds", "load_seconds",
        "prompt_eval_seconds", "eval_seconds",
    )
    seen: set[str] = set()
    pair_treatments: dict[tuple[str, str, str, int], list[str]] = defaultdict(list)
    if len(rows) != len(canonical):
        raise ValueError("A0 evidence must contain exactly 192 rows")
    for row in rows:
        if any(not _has(row, name) for name in schedule_fields + result_fields):
            raise ValueError("A0 evidence is missing required fields")
        model, case_id = str(_get(row, "model_key")), str(_get(row, "case_id"))
        treatment, replicate = str(_get(row, "treatment_kind")), _get(row, "replicate")
        unit_id = str(_get(row, "unit_id"))
        canonical_unit = canonical.get(unit_id)
        telemetry = tuple(_get(row, name) for name in result_fields[-4:])
        valid = (
            canonical_unit is not None
            and all(_get(row, field) == getattr(canonical_unit, field) for field in schedule_fields)
            and type(_get(row, "correct")) is bool
            and isinstance(_get(row, "normalized_answer"), str)
            and bool(_get(row, "normalized_answer"))
            and all(isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 for value in telemetry)
        )
        if not valid or unit_id in seen:
            raise ValueError("A0 evidence does not match the frozen schedule")
        seen.add(unit_id)
        pair_treatments[(model, case_id, str(_get(row, "operating_region")), replicate)].append(treatment)
    if any(sorted(values) != ["HISTORICAL_SEED", "RAW"] for values in pair_treatments.values()) or len(pair_treatments) != 96:
        raise ValueError("A0 evidence pair must contain exactly one RAW and one HISTORICAL_SEED row")
    if seen != set(canonical):
        raise ValueError("A0 evidence has missing or surplus schedule units")


def summarize_a0(rows: Iterable[object]) -> A0Summary:
    frozen_rows = tuple(rows)
    _validate_a0_evidence(frozen_rows)
    noise = calibrate_noise(frozen_rows)
    by_model_rows: dict[str, list[object]] = defaultdict(list)
    for row in frozen_rows:
        by_model_rows[str(_get(row, "model_key", "model"))].append(row)
    models: dict[str, A0ModelSummary] = {}
    for model, model_rows in by_model_rows.items():
        correctness = {}
        for treatment in ("RAW", "HISTORICAL_SEED"):
            treatment_rows = [row for row in model_rows if _get(row, "treatment_kind", "treatment_id", "treatment") == treatment]
            correctness[treatment] = (sum(bool(_get(row, "correct", "success", default=False)) for row in treatment_rows), len(treatment_rows))
        eligible = [cell for key, cell in noise.cells.items() if key[0] == model and cell.eligible]
        region_flags = {}
        effects_by_region = {}
        for region in OPERATING_REGIONS:
            region_rows = [row for row in model_rows if _get(row, "operating_region", "region") == region]
            effects_by_region[region] = paired_effect(region_rows)
            raw = [row for row in region_rows if _get(row, "treatment_kind") == "RAW"]
            historical = [row for row in region_rows if _get(row, "treatment_kind") == "HISTORICAL_SEED"]
            raw_ceiling = len(raw) == 4 and all(bool(_get(row, "correct")) for row in raw)
            historical_ceiling = len(historical) == 4 and all(bool(_get(row, "correct")) for row in historical)
            region_flags[region] = RegionFlags(raw_ceiling, historical_ceiling, raw_ceiling and historical_ceiling)
        diagnostic = model == "DEVSTRAL_24B"
        models[model] = A0ModelSummary(
            correctness=correctness,
            correctness_noise_floor=noise.by_model.get(model, ModelNoise(0.0, 0.0, 0)).correctness_noise_floor,
            answer_noise_floor=noise.by_model.get(model, ModelNoise(0.0, 0.0, 0)).answer_noise_floor,
            paired_effect=paired_effect(model_rows),
            paired_effect_by_region=effects_by_region,
            region_flags=region_flags,
            model_role="DIAGNOSTIC_REFERENCE" if diagnostic else "PRIMARY",
            eligible_for_recipe=not diagnostic,
            saturation_flag=all(flag.saturated for flag in region_flags.values()),
            ceiling_flag=all(flag.raw_ceiling for flag in region_flags.values()),
            runtime_seconds=_distribution(model_rows, "runtime_seconds", "total_duration_seconds", "runtime"),
            load_seconds=_distribution(model_rows, "load_seconds", "load_duration_seconds", "load_duration"),
            prompt_eval_seconds=_distribution(model_rows, "prompt_eval_seconds", "prompt_eval_duration_seconds", "prompt_eval_duration"),
            eval_seconds=_distribution(model_rows, "eval_seconds", "eval_duration_seconds", "eval_duration"),
        )
    return A0Summary(models=models, noise=noise)
