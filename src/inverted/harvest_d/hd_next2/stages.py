"""Frozen Stage 2A-0 planning; later empirical stages deliberately fail closed."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .cases import OPERATING_REGIONS, describe_hd_next2_case, generate_hd_next2_cases
from .config import HDNext2ConfigError, canonical_a0_planner_config, validate_a0_planner_config
from .types import StageId, StagePlan


A0_MODEL_ORDER = ("SMALL_A", "QWEN", "DEVSTRAL_24B")


@dataclass(frozen=True)
class A0Unit:
    unit_id: str
    case_id: str
    partition: str
    operating_region: str
    model_key: str
    treatment_kind: str
    treatment_spec_id: str
    treatment_spec_sha256: str
    treatment_spec: "TreatmentSpec"
    replicate: int
    selection_reason: str
    model_block: str
    model_role: str
    eligible_for_recipe: bool
    execution_position: int
    max_attempts: int = 1
    retry_of_unit_id: None = None


def _a0_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    value = config.get("a0")
    if not isinstance(value, Mapping):
        raise ValueError("frozen A0 configuration is required")
    return value


@dataclass(frozen=True)
class TreatmentSpec:
    information: Mapping[str, str]
    assistance: Mapping[str, str]
    amount: str
    ordering: str
    representation: str
    timing: str
    placement: str


@dataclass(frozen=True)
class FrozenMapping(Mapping[str, str]):
    entries: tuple[tuple[str, str], ...]

    def __getitem__(self, key: str) -> str:
        return dict(self.entries)[key]

    def __iter__(self):
        return (key for key, _ in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


def _frozen(values: Mapping[str, str]) -> FrozenMapping:
    return FrozenMapping(tuple(values.items()))


_RAW_SPEC = TreatmentSpec(_frozen({}), _frozen({}), "NONE", "NONE", "RAW", "NONE", "NONE")
_HISTORICAL_SPEC = TreatmentSpec(
    _frozen({f"I{i}": "ON" if i in {1, 2, 9, 10} else "OFF" for i in range(1, 11)}),
    _frozen({f"A{i}": "TARGET" if i in {1, 3} else "OFF" for i in range(1, 5)}),
    "MINIMUM", "DEFAULT", "ADMISSIBLE_ACTION_MATRIX", "JUST_IN_TIME", "SYSTEM_CONTEXT",
)
A0_TREATMENT_SPECS = MappingProxyType({
    "RAW": _RAW_SPEC,
    "HISTORICAL_SEED": _HISTORICAL_SPEC,
})
_SPEC_IDS = {"RAW": "RAW_V1", "HISTORICAL_SEED": "HD_NEXT_1_WINNER_V1"}


def _spec_sha(kind: str) -> str:
    spec = A0_TREATMENT_SPECS[kind]
    value = ({"kind": "RAW"} if kind == "RAW" else {
        "information": dict(spec.information), "assistance": dict(spec.assistance),
        "amount": spec.amount, "ordering": spec.ordering,
        "representation": spec.representation, "timing": spec.timing, "placement": spec.placement,
    })
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _anchor_cases(cases: Iterable[object], *, seed: int, count: int) -> tuple[object, ...]:
    canonical = tuple(generate_hd_next2_cases("development", seed=seed, per_region=1))
    supplied = tuple(cases)
    canonical_by_id = {case.case_id: case for case in canonical}
    supplied_by_id = {str(getattr(case, "case_id", "")): case for case in supplied}
    if count != len(OPERATING_REGIONS) or len(supplied) != len(canonical) or supplied_by_id != canonical_by_id:
        raise ValueError("A0 requires the exact canonical development case set")
    return canonical


def _build_a0(config: Mapping[str, Any], cases: Iterable[object]) -> StagePlan:
    try:
        validate_a0_planner_config(config)
    except HDNext2ConfigError as exc:
        raise ValueError("frozen A0 planner configuration mismatch") from exc
    frozen = _a0_config(config)
    anchors = _anchor_cases(
        cases,
        seed=int(frozen["development_seed"]),
        count=int(frozen["anchor_case_count"]),
    )
    repetitions = int(frozen["replications_per_cell"])
    treatment_kinds = tuple(frozen["treatment_kinds"])
    units: list[A0Unit] = []
    for model_key in A0_MODEL_ORDER:
        block = f"A0-{model_key}-RESIDENCY"
        diagnostic = model_key == frozen["diagnostic_model"]
        reason = "diagnostic_reference_calibration" if diagnostic else "primary_noise_calibration"
        for case in anchors:
            description = describe_hd_next2_case(case)
            for treatment_kind in treatment_kinds:
                for replicate in range(1, repetitions + 1):
                    position = len(units) + 1
                    case_id = str(getattr(case, "case_id"))
                    unit_id = f"2A-0__{model_key}__{case_id}__{treatment_kind}__R{replicate:02d}"
                    units.append(A0Unit(
                        unit_id=unit_id,
                        case_id=case_id,
                        partition="development",
                        operating_region=description["region"],
                        model_key=model_key,
                        treatment_kind=treatment_kind,
                        treatment_spec_id=_SPEC_IDS[treatment_kind],
                        treatment_spec_sha256=_spec_sha(treatment_kind),
                        treatment_spec=A0_TREATMENT_SPECS[treatment_kind],
                        replicate=replicate,
                        selection_reason=reason,
                        model_block=block,
                        model_role="DIAGNOSTIC_REFERENCE" if diagnostic else "PRIMARY",
                        eligible_for_recipe=not diagnostic,
                        execution_position=position,
                    ))
    forecast = len(units) + int(frozen["non_model_action_forecast"])
    if forecast > int(config["combined_action_ceiling"]):
        raise ValueError("A0 forecast exceeds the combined action ceiling")
    return StagePlan("HD-NEXT-2A-0", StageId.A0, tuple(units), forecast)


def build_canonical_a0_plan() -> StagePlan:
    """Return the frozen A0 schedule used to authenticate result evidence."""
    config = canonical_a0_planner_config()
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    return _build_a0(config, cases)


def build_stage_plans(
    stage: StageId,
    config: Mapping[str, Any],
    cases: Iterable[object],
    registry: object,
    coverage: object,
    prior_analysis: Mapping[str, Any],
) -> tuple[StagePlan, ...]:
    """Build only the controller-approved A0 plan.

    Registry, coverage, and prior analysis are accepted for the stable future
    interface but cannot influence the frozen calibration campaign.
    """
    del registry, coverage, prior_analysis
    stage = StageId(stage)
    if stage is StageId.A0:
        return (_build_a0(config, cases),)
    if stage is StageId.A10:
        reserve = int(config["non_model_action_reserve"])
        return (StagePlan("HD-NEXT-2A-10-DEFERRED", stage, (), reserve),)
    raise NotImplementedError(
        "later stages are deferred until A0/Test-1 evidence is analyzed"
    )
