"""Frozen scientific contracts for V3 Stage-5 operating-surface characterization."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .core import Partition, PromotionState


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SurfaceAxis(str, Enum):
    REASONING_BUDGET = "REASONING_BUDGET"
    TEMPERATURE = "TEMPERATURE"
    CONTEXT_DOSE = "CONTEXT_DOSE"
    REPRESENTATION = "REPRESENTATION"
    ORDER = "ORDER"
    RECURRENCE = "RECURRENCE"
    TIMING = "TIMING"
    PLACEMENT = "PLACEMENT"
    CONTEXT_POSITION = "CONTEXT_POSITION"
    DELIVERY_MODE = "DELIVERY_MODE"
    TRIGGER_MODE = "TRIGGER_MODE"


class SurfaceEvidenceKind(str, Enum):
    SAME_STATE_CAUSAL = "SAME_STATE_CAUSAL"
    HISTORICAL_PRIOR = "HISTORICAL_PRIOR"


class SurfaceDisposition(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    USEFUL_BAND = "USEFUL_BAND"
    PLATEAU = "PLATEAU"
    SATURATED = "SATURATED"
    HARM_BOUNDARY = "HARM_BOUNDARY"
    NEGATIVE_TRANSFER = "NEGATIVE_TRANSFER"
    NO_USEFUL_REGION = "NO_USEFUL_REGION"


def _required(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value):
            raise TypeError("surface mapping keys must be non-blank strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("surface payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"surface payload contains unsupported value: {type(value).__name__}")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("surface payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"surface payload contains unsupported value: {type(value).__name__}")


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        _json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(payload)).hexdigest()[:24]}"


def _strings(name: str, values: tuple[str, ...], *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of strings")
    result = tuple(values)
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{name} must contain non-blank strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must be unique")
    return result


def _surface_value(value: Any) -> Any:
    frozen = _freeze_json(value)
    if isinstance(frozen, Mapping):
        raise TypeError("surface axis values must be scalar or ordered sequences")
    return frozen


@dataclass(frozen=True)
class SurfaceStudy:
    study_id: str
    failure_snapshot_id: str
    mechanism_id: str
    parent_state_hash: str
    partition: Partition
    promotion_state: PromotionState
    decision_id: str
    axes: tuple[SurfaceAxis, ...]
    axis_values: Mapping[str, tuple[Any, ...]]
    decision_critical_reason: str | None = None

    def __post_init__(self) -> None:
        for name in ("study_id", "failure_snapshot_id", "mechanism_id", "decision_id"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        if not isinstance(self.partition, Partition):
            object.__setattr__(self, "partition", Partition(self.partition))
        if not isinstance(self.promotion_state, PromotionState):
            object.__setattr__(self, "promotion_state", PromotionState(self.promotion_state))
        axes = tuple(item if isinstance(item, SurfaceAxis) else SurfaceAxis(item) for item in self.axes)
        if not axes:
            raise ValueError("axes must not be empty")
        if len(set(axes)) != len(axes):
            raise ValueError("axes must be unique")
        object.__setattr__(self, "axes", axes)
        if self.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH/SEALED evidence cannot enter Stage-5 characterization")
        if self.promotion_state is PromotionState.REJECTED:
            raise ValueError("REJECTED mechanisms cannot enter Stage-5 characterization")
        if self.promotion_state is not PromotionState.MOVEMENT:
            if not self.decision_critical_reason or not self.decision_critical_reason.strip():
                raise ValueError("Stage-5 characterization requires MOVEMENT or a decision-critical reason")
        if self.decision_critical_reason is not None:
            _required("decision_critical_reason", self.decision_critical_reason)
        if not isinstance(self.axis_values, Mapping):
            raise TypeError("axis_values must be a mapping")
        normalized: dict[str, tuple[Any, ...]] = {}
        for key, values in self.axis_values.items():
            axis = key if isinstance(key, SurfaceAxis) else SurfaceAxis(key)
            if isinstance(values, (str, bytes, bytearray)):
                raise TypeError("axis values must be sequences")
            frozen_values = tuple(_surface_value(item) for item in values)
            if not frozen_values:
                raise ValueError("axis values must not be empty")
            identities = tuple(json.dumps(_json_value(item), sort_keys=True, separators=(",", ":")) for item in frozen_values)
            if len(set(identities)) != len(identities):
                raise ValueError("axis values must be unique")
            normalized[axis.value] = frozen_values
        if set(normalized) != {axis.value for axis in axes}:
            raise ValueError("axis_values keys must exactly match axes")
        object.__setattr__(self, "axis_values", MappingProxyType(normalized))

    @classmethod
    def create(
        cls,
        *,
        failure_snapshot_id: str,
        mechanism_id: str,
        parent_state_hash: str,
        partition: Partition,
        promotion_state: PromotionState,
        decision_id: str,
        axes: tuple[SurfaceAxis, ...],
        axis_values: Mapping[str, tuple[Any, ...]],
        decision_critical_reason: str | None = None,
    ) -> "SurfaceStudy":
        payload = {
            "failure_snapshot_id": failure_snapshot_id,
            "mechanism_id": mechanism_id,
            "parent_state_hash": parent_state_hash,
            "partition": Partition(partition).value,
            "promotion_state": PromotionState(promotion_state).value,
            "decision_id": decision_id,
            "axes": [SurfaceAxis(axis).value for axis in axes],
            "axis_values": {
                (key.value if isinstance(key, SurfaceAxis) else str(key)): list(values)
                for key, values in axis_values.items()
            },
            "decision_critical_reason": decision_critical_reason,
        }
        return cls(study_id=_stable_id("surface-study", payload), **payload)


@dataclass(frozen=True)
class SurfacePoint:
    surface_point_id: str
    study_id: str
    failure_snapshot_id: str
    mechanism_id: str
    parent_state_hash: str
    partition: Partition
    axis: SurfaceAxis
    value: Any
    decision_id: str
    protected_exploration: bool = False

    def __post_init__(self) -> None:
        for name in ("surface_point_id", "study_id", "failure_snapshot_id", "mechanism_id", "decision_id"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        if not isinstance(self.partition, Partition):
            object.__setattr__(self, "partition", Partition(self.partition))
        if not isinstance(self.axis, SurfaceAxis):
            object.__setattr__(self, "axis", SurfaceAxis(self.axis))
        object.__setattr__(self, "value", _surface_value(self.value))
        if type(self.protected_exploration) is not bool:
            raise TypeError("protected_exploration must be boolean")

    @classmethod
    def create(
        cls,
        *,
        study: SurfaceStudy,
        axis: SurfaceAxis,
        value: Any,
        decision_id: str,
        protected_exploration: bool = False,
    ) -> "SurfacePoint":
        axis = axis if isinstance(axis, SurfaceAxis) else SurfaceAxis(axis)
        if axis not in study.axes:
            raise ValueError("surface axis is not registered by the study")
        frozen_value = _surface_value(value)
        registered = study.axis_values[axis.value]
        if frozen_value not in registered:
            raise ValueError("surface point value is not registered by the study")
        payload = {
            "study_id": study.study_id,
            "failure_snapshot_id": study.failure_snapshot_id,
            "mechanism_id": study.mechanism_id,
            "parent_state_hash": study.parent_state_hash,
            "partition": study.partition.value,
            "axis": axis.value,
            "value": frozen_value,
            "decision_id": decision_id,
            "protected_exploration": protected_exploration,
        }
        return cls(surface_point_id=_stable_id("surface-point", payload), **payload)


@dataclass(frozen=True)
class SurfaceObservation:
    observation_id: str
    surface_point_id: str
    study_id: str
    failure_snapshot_id: str
    mechanism_id: str
    parent_state_hash: str
    axis: SurfaceAxis
    value: Any
    decision_id: str
    protected_exploration: bool
    evidence_kind: SurfaceEvidenceKind
    replay_result_ids: tuple[str, ...] = ()
    source_evidence_refs: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("observation_id", "surface_point_id", "study_id", "failure_snapshot_id", "mechanism_id"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        if not isinstance(self.axis, SurfaceAxis):
            object.__setattr__(self, "axis", SurfaceAxis(self.axis))
        object.__setattr__(self, "value", _surface_value(self.value))
        _required("decision_id", self.decision_id)
        if type(self.protected_exploration) is not bool:
            raise TypeError("protected_exploration must be boolean")
        if not isinstance(self.evidence_kind, SurfaceEvidenceKind):
            object.__setattr__(self, "evidence_kind", SurfaceEvidenceKind(self.evidence_kind))
        replay_ids = _strings("replay_result_ids", self.replay_result_ids, allow_empty=True)
        refs = _strings("source_evidence_refs", self.source_evidence_refs, allow_empty=True)
        if self.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL:
            if not replay_ids or refs:
                raise ValueError("SAME_STATE_CAUSAL requires replay_result_ids and forbids source_evidence_refs")
        else:
            if not refs or replay_ids:
                raise ValueError("HISTORICAL_PRIOR requires source_evidence_refs and forbids replay_result_ids")
        object.__setattr__(self, "replay_result_ids", replay_ids)
        object.__setattr__(self, "source_evidence_refs", refs)
        if not isinstance(self.metrics, Mapping):
            raise TypeError("metrics must be a mapping")
        object.__setattr__(self, "metrics", _freeze_json(self.metrics))

    @classmethod
    def create(
        cls,
        *,
        point: SurfacePoint,
        evidence_kind: SurfaceEvidenceKind,
        replay_result_ids: tuple[str, ...] = (),
        source_evidence_refs: tuple[str, ...] = (),
        metrics: Mapping[str, Any] | None = None,
    ) -> "SurfaceObservation":
        payload = {
            "surface_point_id": point.surface_point_id,
            "study_id": point.study_id,
            "failure_snapshot_id": point.failure_snapshot_id,
            "mechanism_id": point.mechanism_id,
            "parent_state_hash": point.parent_state_hash,
            "axis": point.axis.value,
            "value": point.value,
            "decision_id": point.decision_id,
            "protected_exploration": point.protected_exploration,
            "evidence_kind": SurfaceEvidenceKind(evidence_kind).value,
            "replay_result_ids": list(replay_result_ids),
            "source_evidence_refs": list(source_evidence_refs),
            "metrics": {} if metrics is None else dict(metrics),
        }
        return cls(observation_id=_stable_id("surface-observation", payload), **payload)


@dataclass(frozen=True)
class SurfaceCallGeometry:
    minimum_physical_calls: int
    expected_physical_calls: int
    worst_case_physical_calls: int
    protected_exploration_calls: int = 0

    def __post_init__(self) -> None:
        values = (
            self.minimum_physical_calls,
            self.expected_physical_calls,
            self.worst_case_physical_calls,
            self.protected_exploration_calls,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("surface call geometry values must be non-negative integers")
        if not self.minimum_physical_calls <= self.expected_physical_calls <= self.worst_case_physical_calls:
            raise ValueError("minimum, expected, and worst physical calls must be ordered")
        if self.protected_exploration_calls > self.worst_case_physical_calls:
            raise ValueError("protected exploration calls cannot exceed worst-case calls")


@dataclass(frozen=True)
class SurfaceBand:
    axis: SurfaceAxis
    disposition: SurfaceDisposition
    lower_useful: Any | None
    upper_useful: Any | None
    recommended_region: tuple[Any, ...]
    harm_onset: Any | None
    evidence_observation_ids: tuple[str, ...]
    unresolved_edges: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.axis, SurfaceAxis):
            object.__setattr__(self, "axis", SurfaceAxis(self.axis))
        if not isinstance(self.disposition, SurfaceDisposition):
            object.__setattr__(self, "disposition", SurfaceDisposition(self.disposition))
        object.__setattr__(self, "lower_useful", _surface_value(self.lower_useful))
        object.__setattr__(self, "upper_useful", _surface_value(self.upper_useful))
        object.__setattr__(self, "harm_onset", _surface_value(self.harm_onset))
        object.__setattr__(self, "recommended_region", tuple(_surface_value(item) for item in self.recommended_region))
        object.__setattr__(self, "unresolved_edges", tuple(_surface_value(item) for item in self.unresolved_edges))
        object.__setattr__(self, "evidence_observation_ids", _strings("evidence_observation_ids", self.evidence_observation_ids))


@dataclass(frozen=True)
class OperatingSurfaceProfile:
    profile_id: str
    study_id: str
    failure_snapshot_id: str
    mechanism_id: str
    parent_state_hash: str
    partition: Partition
    axis: SurfaceAxis
    disposition: SurfaceDisposition
    lower_useful: Any | None
    upper_useful: Any | None
    recommended_region: tuple[Any, ...]
    harm_onset: Any | None
    evidence_refs: tuple[str, ...]
    unresolved_edges: tuple[Any, ...]
    call_geometry: SurfaceCallGeometry
    promotion_ceiling: PromotionState = PromotionState.MOVEMENT

    def __post_init__(self) -> None:
        for name in ("profile_id", "study_id", "failure_snapshot_id", "mechanism_id"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        if not isinstance(self.partition, Partition):
            object.__setattr__(self, "partition", Partition(self.partition))
        if not isinstance(self.axis, SurfaceAxis):
            object.__setattr__(self, "axis", SurfaceAxis(self.axis))
        if not isinstance(self.disposition, SurfaceDisposition):
            object.__setattr__(self, "disposition", SurfaceDisposition(self.disposition))
        if not isinstance(self.promotion_ceiling, PromotionState):
            object.__setattr__(self, "promotion_ceiling", PromotionState(self.promotion_ceiling))
        if self.promotion_ceiling is not PromotionState.MOVEMENT:
            raise ValueError("Plan 3 operating-surface profiles are capped at MOVEMENT")
        if not isinstance(self.call_geometry, SurfaceCallGeometry):
            raise TypeError("call_geometry must be SurfaceCallGeometry")
        object.__setattr__(self, "lower_useful", _surface_value(self.lower_useful))
        object.__setattr__(self, "upper_useful", _surface_value(self.upper_useful))
        object.__setattr__(self, "harm_onset", _surface_value(self.harm_onset))
        object.__setattr__(self, "recommended_region", tuple(_surface_value(item) for item in self.recommended_region))
        object.__setattr__(self, "unresolved_edges", tuple(_surface_value(item) for item in self.unresolved_edges))
        object.__setattr__(self, "evidence_refs", _strings("evidence_refs", self.evidence_refs))

    @classmethod
    def create(
        cls,
        *,
        study: SurfaceStudy,
        band: SurfaceBand,
        evidence_refs: tuple[str, ...],
        call_geometry: SurfaceCallGeometry,
        promotion_ceiling: PromotionState = PromotionState.MOVEMENT,
    ) -> "OperatingSurfaceProfile":
        if band.axis not in study.axes:
            raise ValueError("surface band axis is not registered by the study")
        promotion_ceiling = PromotionState(promotion_ceiling)
        if promotion_ceiling is not PromotionState.MOVEMENT:
            raise ValueError("Plan 3 operating-surface profiles are capped at MOVEMENT")
        payload = {
            "study_id": study.study_id,
            "failure_snapshot_id": study.failure_snapshot_id,
            "mechanism_id": study.mechanism_id,
            "parent_state_hash": study.parent_state_hash,
            "partition": study.partition.value,
            "axis": band.axis.value,
            "disposition": band.disposition.value,
            "lower_useful": band.lower_useful,
            "upper_useful": band.upper_useful,
            "recommended_region": list(band.recommended_region),
            "harm_onset": band.harm_onset,
            "evidence_refs": list(evidence_refs),
            "unresolved_edges": list(band.unresolved_edges),
            "call_geometry": {
                "minimum_physical_calls": call_geometry.minimum_physical_calls,
                "expected_physical_calls": call_geometry.expected_physical_calls,
                "worst_case_physical_calls": call_geometry.worst_case_physical_calls,
                "protected_exploration_calls": call_geometry.protected_exploration_calls,
            },
            "promotion_ceiling": promotion_ceiling.value,
        }
        return cls(profile_id=_stable_id("surface-profile", payload), call_geometry=call_geometry, **{
            key: value for key, value in payload.items() if key != "call_geometry"
        })
