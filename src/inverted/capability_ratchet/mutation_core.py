"""Frozen, zero-inference contracts for Stage-6 mutation generalization."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class MutationAxis(str, Enum):
    NUMBERS_ENTITIES = "NUMBERS_ENTITIES"
    DEPENDENCY_DEPTH = "DEPENDENCY_DEPTH"
    REQUIREMENT_COUNT = "REQUIREMENT_COUNT"
    ACTION_SPACE_SIZE = "ACTION_SPACE_SIZE"
    CRITICAL_INFORMATION_POSITION = "CRITICAL_INFORMATION_POSITION"
    DISTRACTORS = "DISTRACTORS"
    EVIDENCE_STATE = "EVIDENCE_STATE"
    AUTHORITY_STATE = "AUTHORITY_STATE"
    REVERSIBILITY_CONSEQUENCE = "REVERSIBILITY_CONSEQUENCE"
    TOOL_AVAILABILITY = "TOOL_AVAILABILITY"
    CONTEXT_PRESSURE = "CONTEXT_PRESSURE"
    ORDER = "ORDER"
    RECOVERY_OPPORTUNITY = "RECOVERY_OPPORTUNITY"


class MutationOrigin(str, Enum):
    SYNTHETIC_NEIGHBORHOOD = "SYNTHETIC_NEIGHBORHOOD"
    NATURAL_OBSERVATION = "NATURAL_OBSERVATION"


class GeneralizationClass(str, Enum):
    INSTANCE_PATCH = "INSTANCE_PATCH"
    LOCAL_MECHANISM = "LOCAL_MECHANISM"
    REGION_MECHANISM = "REGION_MECHANISM"
    CROSS_REGION_MECHANISM = "CROSS_REGION_MECHANISM"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"


class MutationDirection(str, Enum):
    EASIER = "EASIER"
    LATERAL = "LATERAL"
    HARDER = "HARDER"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mutation mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("mutation numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported mutation value: {type(value).__name__}")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported mutation value: {type(value).__name__}")


def _required(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _canonical_id(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:20]}"


@dataclass(frozen=True)
class MutationSpec:
    axis: MutationAxis
    direction: MutationDirection
    value: Any
    structural_region_id: str
    decision_id: str = "D12"
    protected: bool = False
    spec_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.axis, MutationAxis):
            object.__setattr__(self, "axis", MutationAxis(self.axis))
        if not isinstance(self.direction, MutationDirection):
            object.__setattr__(self, "direction", MutationDirection(self.direction))
        _required("structural_region_id", self.structural_region_id)
        _required("decision_id", self.decision_id)
        if type(self.protected) is not bool:
            raise TypeError("protected must be boolean")
        frozen = _freeze(self.value)
        object.__setattr__(self, "value", frozen)
        expected = _canonical_id(
            "mutation-spec",
            {
                "axis": self.axis,
                "direction": self.direction,
                "value": frozen,
                "structural_region_id": self.structural_region_id,
                "decision_id": self.decision_id,
                "protected": self.protected,
            },
        )
        if self.spec_id is not None and self.spec_id != expected:
            raise ValueError("spec_id does not match canonical mutation spec")
        object.__setattr__(self, "spec_id", expected)


@dataclass(frozen=True)
class MutationPolicy:
    min_local_successes: int = 2
    min_region_successes: int = 4
    min_region_axes: int = 3
    min_cross_region_successes: int = 6
    min_cross_regions: int = 2
    min_promotion_successes: int = 6
    min_promotion_axes: int = 4
    min_harder_successes: int = 2
    min_success_rate: float = 0.80
    max_protected_failures: int = 0

    def __post_init__(self) -> None:
        for name in (
            "min_local_successes",
            "min_region_successes",
            "min_region_axes",
            "min_cross_region_successes",
            "min_cross_regions",
            "min_promotion_successes",
            "min_promotion_axes",
            "min_harder_successes",
            "max_protected_failures",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.min_success_rate, (int, float)) or isinstance(self.min_success_rate, bool):
            raise TypeError("min_success_rate must be numeric")
        if not 0.0 <= float(self.min_success_rate) <= 1.0:
            raise ValueError("min_success_rate must be between 0 and 1")
        object.__setattr__(self, "min_success_rate", float(self.min_success_rate))

    def to_payload(self) -> dict[str, Any]:
        return {
            "min_local_successes": self.min_local_successes,
            "min_region_successes": self.min_region_successes,
            "min_region_axes": self.min_region_axes,
            "min_cross_region_successes": self.min_cross_region_successes,
            "min_cross_regions": self.min_cross_regions,
            "min_promotion_successes": self.min_promotion_successes,
            "min_promotion_axes": self.min_promotion_axes,
            "min_harder_successes": self.min_harder_successes,
            "min_success_rate": self.min_success_rate,
            "max_protected_failures": self.max_protected_failures,
        }


@dataclass(frozen=True)
class GeneralizationProfile:
    profile_id: str
    study_id: str
    failure_snapshot_id: str
    mechanism_id: str
    policy: MutationPolicy
    mutation_result_ids: tuple[str, ...]
    successful_mutation_fixture_ids: tuple[str, ...]
    failed_mutation_fixture_ids: tuple[str, ...]
    axis_successes: Mapping[str, int]
    region_successes: Mapping[str, int]
    harder_successes: int
    success_rate: float
    protected_failures: tuple[str, ...]
    classification: GeneralizationClass
    unresolved_boundaries: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("profile_id", "study_id", "failure_snapshot_id", "mechanism_id"):
            _required(name, getattr(self, name))
        if not isinstance(self.policy, MutationPolicy):
            object.__setattr__(self, "policy", MutationPolicy(**dict(self.policy)))
        if not isinstance(self.classification, GeneralizationClass):
            object.__setattr__(self, "classification", GeneralizationClass(self.classification))
        if not isinstance(self.harder_successes, int) or isinstance(self.harder_successes, bool) or self.harder_successes < 0:
            raise ValueError("harder_successes must be a non-negative integer")
        if not isinstance(self.success_rate, (int, float)) or isinstance(self.success_rate, bool):
            raise TypeError("success_rate must be numeric")
        if not 0.0 <= float(self.success_rate) <= 1.0:
            raise ValueError("success_rate must be between 0 and 1")
        object.__setattr__(self, "success_rate", float(self.success_rate))
        for name in (
            "mutation_result_ids",
            "successful_mutation_fixture_ids",
            "failed_mutation_fixture_ids",
            "protected_failures",
            "unresolved_boundaries",
        ):
            value = getattr(self, name)
            if isinstance(value, str) or not isinstance(value, (list, tuple)):
                raise TypeError(f"{name} must be a sequence")
            object.__setattr__(self, name, tuple(value))
        for name in ("axis_successes", "region_successes", "metadata"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping")
            object.__setattr__(self, name, _freeze(value))

    @property
    def promotion_ceiling(self):
        from .core import PromotionState

        return PromotionState.TIER_CANDIDATE
