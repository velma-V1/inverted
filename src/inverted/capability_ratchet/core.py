"""Frozen, zero-inference data contracts for the V3 replay registry."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias


class ReplayRecordType(str, Enum):
    FAILURE_FIXTURE = "FAILURE_FIXTURE"
    REPLAY_REQUEST = "REPLAY_REQUEST"
    REPLAY_RESULT = "REPLAY_RESULT"
    MUTATION_FIXTURE = "MUTATION_FIXTURE"
    MECHANISM_LABEL = "MECHANISM_LABEL"
    PROMOTION_EVENT = "PROMOTION_EVENT"
    SUPERSESSION = "SUPERSESSION"


class ReplayMode(str, Enum):
    EXACT = "EXACT"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    CROSS_MODEL = "CROSS_MODEL"


class PromotionState(str, Enum):
    UNASSESSED = "UNASSESSED"
    MOVEMENT = "MOVEMENT"
    TIER_CANDIDATE = "TIER_CANDIDATE"
    CERTIFIED = "CERTIFIED"
    REJECTED = "REJECTED"


class Partition(str, Enum):
    HISTORICAL = "HISTORICAL"
    DEVELOPMENT = "DEVELOPMENT"
    TRAINING = "TRAINING"
    FRESH = "FRESH"
    SEALED = "SEALED"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _required(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _sha256(name: str, value: str | None, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported replay payload value: {type(value).__name__}")


def _coerce_enum(instance: object, name: str, enum_type: type[Enum]) -> None:
    value = getattr(instance, name)
    if not isinstance(value, enum_type):
        object.__setattr__(instance, name, enum_type(value))


def _freeze_field(instance: object, name: str) -> None:
    object.__setattr__(instance, name, _freeze(getattr(instance, name)))


@dataclass(frozen=True)
class FailureFixture:
    failure_snapshot_id: str
    source_campaign_id: str
    source_trial_id: str
    focus_observation_id: str
    focus_task_id: str
    batch_task_ids: tuple[str, ...]
    family: str
    failure_classes: tuple[str, ...]
    source_model_id: str
    source_model_digest: str
    source_runtime: Mapping[str, Any]
    inference_profile: Mapping[str, Any]
    inference_seed: int
    partition: Partition
    model_visible_asset_sha256: str
    oracle_ref: str
    expected_contract: str
    source_evidence_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    promotion_state: PromotionState = PromotionState.UNASSESSED
    parent_failure_snapshot_id: str | None = None
    parent_state_hash: str | None = None
    record_id: str | None = None
    record_type: ReplayRecordType = field(
        default=ReplayRecordType.FAILURE_FIXTURE, init=False
    )

    def __post_init__(self) -> None:
        _coerce_enum(self, "partition", Partition)
        _coerce_enum(self, "promotion_state", PromotionState)
        for name in (
            "failure_snapshot_id",
            "source_campaign_id",
            "source_trial_id",
            "focus_observation_id",
            "focus_task_id",
            "family",
            "source_model_id",
            "source_model_digest",
            "model_visible_asset_sha256",
            "oracle_ref",
            "expected_contract",
        ):
            _required(name, getattr(self, name))
        if not self.batch_task_ids or self.focus_task_id not in self.batch_task_ids:
            raise ValueError("batch_task_ids must contain focus_task_id")
        if len(set(self.batch_task_ids)) != len(self.batch_task_ids):
            raise ValueError("batch_task_ids must be unique")
        if not self.failure_classes:
            raise ValueError("failure_classes must not be empty")
        _sha256("model_visible_asset_sha256", self.model_visible_asset_sha256)
        _sha256("parent_state_hash", self.parent_state_hash, optional=True)
        _sha256("record_id", self.record_id, optional=True)
        if self.parent_failure_snapshot_id is not None:
            _required("parent_failure_snapshot_id", self.parent_failure_snapshot_id)
        object.__setattr__(self, "batch_task_ids", tuple(self.batch_task_ids))
        object.__setattr__(self, "failure_classes", tuple(self.failure_classes))
        object.__setattr__(self, "source_evidence_refs", tuple(self.source_evidence_refs))
        for name in ("source_runtime", "inference_profile", "metadata"):
            _freeze_field(self, name)


@dataclass(frozen=True)
class ReplayRequest:
    replay_request_id: str
    parent_failure_snapshot_id: str
    decision_id: str
    hypothesis_id: str
    mode: ReplayMode
    target_model_id: str
    target_model_digest: str
    partition: Partition
    changed_dimensions: tuple[str, ...] = ()
    intervention_id: str | None = None
    counterfactual_group_id: str | None = None
    overrides: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    record_id: str | None = None
    record_type: ReplayRecordType = field(
        default=ReplayRecordType.REPLAY_REQUEST, init=False
    )

    def __post_init__(self) -> None:
        _coerce_enum(self, "mode", ReplayMode)
        _coerce_enum(self, "partition", Partition)
        for name in (
            "replay_request_id",
            "parent_failure_snapshot_id",
            "decision_id",
            "hypothesis_id",
            "target_model_id",
            "target_model_digest",
        ):
            _required(name, getattr(self, name))
        dimensions = tuple(self.changed_dimensions)
        if any(not isinstance(item, str) or not item.strip() for item in dimensions):
            raise ValueError("changed_dimensions must contain non-blank names")
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("changed_dimensions must be unique")
        if self.mode is ReplayMode.EXACT and dimensions:
            raise ValueError("EXACT replay forbids changed dimensions")
        if self.mode is ReplayMode.COUNTERFACTUAL and not dimensions:
            raise ValueError("COUNTERFACTUAL replay requires changed dimensions")
        if self.mode is ReplayMode.CROSS_MODEL and "target_model" not in dimensions:
            raise ValueError(
                "CROSS_MODEL replay requires target_model in changed dimensions"
            )
        _sha256("record_id", self.record_id, optional=True)
        object.__setattr__(self, "changed_dimensions", dimensions)
        for name in ("overrides", "metadata"):
            _freeze_field(self, name)

    @classmethod
    def for_exact(
        cls,
        fixture: FailureFixture,
        *,
        decision_id: str,
        hypothesis_id: str,
        request_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ReplayRequest:
        if request_id is None:
            identity = json.dumps(
                {
                    "decision_id": decision_id,
                    "failure_snapshot_id": fixture.failure_snapshot_id,
                    "hypothesis_id": hypothesis_id,
                    "mode": ReplayMode.EXACT.value,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            request_id = f"replay-request-{hashlib.sha256(identity).hexdigest()[:20]}"
        return cls(
            replay_request_id=request_id,
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            decision_id=decision_id,
            hypothesis_id=hypothesis_id,
            mode=ReplayMode.EXACT,
            target_model_id=fixture.source_model_id,
            target_model_digest=fixture.source_model_digest,
            partition=fixture.partition,
            metadata={} if metadata is None else metadata,
        )


@dataclass(frozen=True)
class ReplayResult:
    replay_result_id: str
    replay_request_id: str
    parent_failure_snapshot_id: str
    mode: ReplayMode
    target_model_id: str
    target_model_digest: str
    partition: Partition
    completed: bool
    semantic_pass: bool
    contract_pass: bool
    output_asset_sha256: str
    raw_call_asset_sha256: str
    failure_classes: tuple[str, ...] = ()
    child_failure_snapshot_id: str | None = None
    adapter_changes: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    record_id: str | None = None
    record_type: ReplayRecordType = field(
        default=ReplayRecordType.REPLAY_RESULT, init=False
    )

    def __post_init__(self) -> None:
        _coerce_enum(self, "mode", ReplayMode)
        _coerce_enum(self, "partition", Partition)
        for name in (
            "replay_result_id",
            "replay_request_id",
            "parent_failure_snapshot_id",
            "target_model_id",
            "target_model_digest",
        ):
            _required(name, getattr(self, name))
        _sha256("output_asset_sha256", self.output_asset_sha256)
        _sha256("raw_call_asset_sha256", self.raw_call_asset_sha256)
        _sha256("record_id", self.record_id, optional=True)
        if self.child_failure_snapshot_id is not None:
            _required("child_failure_snapshot_id", self.child_failure_snapshot_id)
        object.__setattr__(self, "failure_classes", tuple(self.failure_classes))
        for name in ("adapter_changes", "metrics", "metadata"):
            _freeze_field(self, name)


ReplayRecord: TypeAlias = FailureFixture | ReplayRequest | ReplayResult


def to_payload(value: ReplayRecord) -> dict[str, Any]:
    """Serialize a canonical replay record without relying on dataclass internals."""

    if isinstance(value, FailureFixture):
        payload = {
            "record_type": value.record_type,
            "failure_snapshot_id": value.failure_snapshot_id,
            "source_campaign_id": value.source_campaign_id,
            "source_trial_id": value.source_trial_id,
            "focus_observation_id": value.focus_observation_id,
            "focus_task_id": value.focus_task_id,
            "batch_task_ids": value.batch_task_ids,
            "family": value.family,
            "failure_classes": value.failure_classes,
            "source_model_id": value.source_model_id,
            "source_model_digest": value.source_model_digest,
            "source_runtime": value.source_runtime,
            "inference_profile": value.inference_profile,
            "inference_seed": value.inference_seed,
            "partition": value.partition,
            "model_visible_asset_sha256": value.model_visible_asset_sha256,
            "oracle_ref": value.oracle_ref,
            "expected_contract": value.expected_contract,
            "source_evidence_refs": value.source_evidence_refs,
            "metadata": value.metadata,
            "promotion_state": value.promotion_state,
            "parent_failure_snapshot_id": value.parent_failure_snapshot_id,
            "parent_state_hash": value.parent_state_hash,
            "record_id": value.record_id,
        }
    elif isinstance(value, ReplayRequest):
        payload = {
            "record_type": value.record_type,
            "replay_request_id": value.replay_request_id,
            "parent_failure_snapshot_id": value.parent_failure_snapshot_id,
            "decision_id": value.decision_id,
            "hypothesis_id": value.hypothesis_id,
            "mode": value.mode,
            "target_model_id": value.target_model_id,
            "target_model_digest": value.target_model_digest,
            "partition": value.partition,
            "changed_dimensions": value.changed_dimensions,
            "intervention_id": value.intervention_id,
            "counterfactual_group_id": value.counterfactual_group_id,
            "overrides": value.overrides,
            "metadata": value.metadata,
            "record_id": value.record_id,
        }
    elif isinstance(value, ReplayResult):
        payload = {
            "record_type": value.record_type,
            "replay_result_id": value.replay_result_id,
            "replay_request_id": value.replay_request_id,
            "parent_failure_snapshot_id": value.parent_failure_snapshot_id,
            "mode": value.mode,
            "target_model_id": value.target_model_id,
            "target_model_digest": value.target_model_digest,
            "partition": value.partition,
            "completed": value.completed,
            "semantic_pass": value.semantic_pass,
            "contract_pass": value.contract_pass,
            "output_asset_sha256": value.output_asset_sha256,
            "raw_call_asset_sha256": value.raw_call_asset_sha256,
            "failure_classes": value.failure_classes,
            "child_failure_snapshot_id": value.child_failure_snapshot_id,
            "adapter_changes": value.adapter_changes,
            "metrics": value.metrics,
            "metadata": value.metadata,
            "record_id": value.record_id,
        }
    else:
        raise TypeError(f"unsupported replay record: {type(value).__name__}")
    return {key: _json_value(item) for key, item in payload.items() if item is not None}


def from_payload(payload: Mapping[str, Any]) -> ReplayRecord:
    """Parse and validate one explicitly typed replay-registry payload."""

    if not isinstance(payload, Mapping):
        raise TypeError("replay payload must be a mapping")
    raw = dict(payload)
    try:
        record_type = ReplayRecordType(raw.pop("record_type"))
    except KeyError as exc:
        raise ValueError("record_type is required") from exc

    if record_type is ReplayRecordType.FAILURE_FIXTURE:
        return FailureFixture(**raw)
    if record_type is ReplayRecordType.REPLAY_REQUEST:
        return ReplayRequest(**raw)
    if record_type is ReplayRecordType.REPLAY_RESULT:
        return ReplayResult(**raw)
    raise ValueError(f"unsupported replay record type: {record_type.value}")
