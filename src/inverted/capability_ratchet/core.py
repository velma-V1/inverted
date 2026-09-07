"""Frozen, zero-inference data contracts for the V3 replay registry."""

from __future__ import annotations

import hashlib
import json
import math
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

_IMMUTABLE_REPLAY_DIMENSIONS = frozenset({
    "source_model_id", "source_model_digest", "target_model_id",
    "target_model_digest", "partition",
    "parent_failure_snapshot_id", "parent_state_hash", "state_hash",
    "failure_snapshot_id", "record_id", "record_type",
    "source_campaign_id", "source_trial_id",
})


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
        if any(not isinstance(key, str) for key in value):
            raise TypeError("replay mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("replay payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported replay payload value: {type(value).__name__}")


def _freeze_mapping(instance: object, name: str) -> None:
    value = getattr(instance, name)
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    object.__setattr__(instance, name, _freeze(value))


def _string_tuple(name: str, value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence of strings")
    items = tuple(value)
    if not allow_empty and not items:
        raise ValueError(f"{name} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise TypeError(f"{name} must contain non-blank strings")
    return items


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("replay payload numbers must be finite")
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
    state_hash: str
    oracle_ref: str
    expected_contract: str
    source_evidence_refs: tuple[str, ...]
    forensic_asset_sha256: str | None = None
    oracle_asset_sha256: str | None = None
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
        batch_task_ids = _string_tuple("batch_task_ids", self.batch_task_ids)
        if self.focus_task_id not in batch_task_ids:
            raise ValueError("batch_task_ids must contain focus_task_id")
        if len(set(batch_task_ids)) != len(batch_task_ids):
            raise ValueError("batch_task_ids must be unique")
        failure_classes = _string_tuple("failure_classes", self.failure_classes)
        source_evidence_refs = _string_tuple("source_evidence_refs", self.source_evidence_refs)
        if not isinstance(self.inference_seed, int) or isinstance(self.inference_seed, bool):
            raise TypeError("inference_seed must be an integer")
        _sha256("model_visible_asset_sha256", self.model_visible_asset_sha256)
        _sha256("state_hash", self.state_hash)
        _sha256("parent_state_hash", self.parent_state_hash, optional=True)
        _sha256("forensic_asset_sha256", self.forensic_asset_sha256, optional=True)
        _sha256("oracle_asset_sha256", self.oracle_asset_sha256, optional=True)
        _sha256("record_id", self.record_id, optional=True)
        has_parent_id = self.parent_failure_snapshot_id is not None
        has_parent_hash = self.parent_state_hash is not None
        if has_parent_id != has_parent_hash:
            raise ValueError("parent_failure_snapshot_id and parent_state_hash must be supplied together")
        if has_parent_id:
            _required("parent_failure_snapshot_id", self.parent_failure_snapshot_id)
            if self.parent_failure_snapshot_id == self.failure_snapshot_id:
                raise ValueError("parent_failure_snapshot_id must differ from failure_snapshot_id")
        object.__setattr__(self, "batch_task_ids", batch_task_ids)
        object.__setattr__(self, "failure_classes", failure_classes)
        object.__setattr__(self, "source_evidence_refs", source_evidence_refs)
        for name in ("source_runtime", "inference_profile", "metadata"):
            _freeze_mapping(self, name)


@dataclass(frozen=True)
class ReplayRequest:
    replay_request_id: str
    failure_snapshot_id: str
    parent_failure_snapshot_id: str
    parent_state_hash: str
    decision_id: str
    hypothesis_id: str
    expected_causal_implication: str
    mode: ReplayMode
    source_model_id: str
    source_model_digest: str
    target_model_id: str
    target_model_digest: str
    partition: Partition
    changed_dimensions: tuple[str, ...] = ()
    intervention_id: str | None = None
    counterfactual_group_id: str | None = None
    overrides: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    record_id: str | None = None
    record_type: ReplayRecordType = field(default=ReplayRecordType.REPLAY_REQUEST, init=False)

    def __post_init__(self) -> None:
        _coerce_enum(self, "mode", ReplayMode)
        _coerce_enum(self, "partition", Partition)
        for name in ("replay_request_id", "failure_snapshot_id", "parent_failure_snapshot_id", "decision_id",
                     "hypothesis_id", "expected_causal_implication", "source_model_id",
                     "source_model_digest", "target_model_id", "target_model_digest"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        dimensions = _string_tuple("changed_dimensions", self.changed_dimensions, allow_empty=True)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("changed_dimensions must be unique")
        _freeze_mapping(self, "overrides")
        _freeze_mapping(self, "metadata")
        override_keys = set(self.overrides)
        same_model = (self.target_model_id == self.source_model_id and
                      self.target_model_digest == self.source_model_digest)
        dimension_set = set(dimensions)
        if self.mode is ReplayMode.EXACT:
            if dimensions or override_keys or not same_model:
                raise ValueError("EXACT replay forbids changes and requires source model provenance")
        elif dimension_set & _IMMUTABLE_REPLAY_DIMENSIONS:
            raise ValueError("replay changed_dimensions contain immutable provenance fields")
        elif self.mode is ReplayMode.COUNTERFACTUAL:
            if not dimensions or not same_model or "target_model" in dimensions:
                raise ValueError("COUNTERFACTUAL replay requires same source model and declared non-model changes")
            if override_keys != dimension_set:
                raise ValueError("COUNTERFACTUAL changed_dimensions must exactly match overrides")
        elif self.mode is ReplayMode.CROSS_MODEL:
            if "target_model" not in dimensions or same_model:
                raise ValueError("CROSS_MODEL replay requires a different target model and target_model dimension")
            if override_keys != (dimension_set - {"target_model"}):
                raise ValueError("CROSS_MODEL non-model changed_dimensions must exactly match overrides")
        if self.intervention_id is None:
            payload = {"mode": self.mode.value, "dimensions": list(dimensions),
                       "overrides": _json_value(self.overrides),
                       "target_model_id": self.target_model_id,
                       "target_model_digest": self.target_model_digest}
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            object.__setattr__(self, "intervention_id", f"intervention-{digest[:20]}")
        else:
            _required("intervention_id", self.intervention_id)
        if self.counterfactual_group_id is None:
            group = hashlib.sha256(f"{self.parent_failure_snapshot_id}:{self.parent_state_hash}".encode("utf-8")).hexdigest()
            object.__setattr__(self, "counterfactual_group_id", f"cf-group-{group[:20]}")
        else:
            _required("counterfactual_group_id", self.counterfactual_group_id)
        _sha256("record_id", self.record_id, optional=True)
        object.__setattr__(self, "changed_dimensions", dimensions)

    @classmethod
    def for_exact(cls, fixture: FailureFixture, *, decision_id: str, hypothesis_id: str,
                  request_id: str | None = None, metadata: Mapping[str, Any] | None = None) -> ReplayRequest:
        if request_id is None:
            identity = json.dumps({"decision_id": decision_id, "failure_snapshot_id": fixture.failure_snapshot_id,
                                   "hypothesis_id": hypothesis_id, "mode": ReplayMode.EXACT.value},
                                  sort_keys=True, separators=(",", ":")).encode("utf-8")
            request_id = f"replay-request-{hashlib.sha256(identity).hexdigest()[:20]}"
        return cls(replay_request_id=request_id, failure_snapshot_id=fixture.failure_snapshot_id,
                   parent_failure_snapshot_id=fixture.failure_snapshot_id,
                   parent_state_hash=fixture.state_hash, decision_id=decision_id, hypothesis_id=hypothesis_id,
                   expected_causal_implication="measure exact failure reproducibility without intervention",
                   mode=ReplayMode.EXACT, source_model_id=fixture.source_model_id,
                   source_model_digest=fixture.source_model_digest, target_model_id=fixture.source_model_id,
                   target_model_digest=fixture.source_model_digest, partition=fixture.partition,
                   metadata={} if metadata is None else metadata)


@dataclass(frozen=True)
class ReplayResult:
    replay_result_id: str
    replay_request_id: str
    failure_snapshot_id: str
    parent_failure_snapshot_id: str
    parent_state_hash: str
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
    record_type: ReplayRecordType = field(default=ReplayRecordType.REPLAY_RESULT, init=False)

    def __post_init__(self) -> None:
        _coerce_enum(self, "mode", ReplayMode)
        _coerce_enum(self, "partition", Partition)
        for name in ("replay_result_id", "replay_request_id", "failure_snapshot_id", "parent_failure_snapshot_id",
                     "target_model_id", "target_model_digest"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        for name in ("completed", "semantic_pass", "contract_pass"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        _sha256("output_asset_sha256", self.output_asset_sha256)
        _sha256("raw_call_asset_sha256", self.raw_call_asset_sha256)
        _sha256("record_id", self.record_id, optional=True)
        failure_classes = _string_tuple("failure_classes", self.failure_classes, allow_empty=True)
        failed = (not self.completed or not self.semantic_pass or not self.contract_pass or bool(failure_classes))
        if failed and self.child_failure_snapshot_id is None:
            raise ValueError("child_failure_snapshot_id is required when replay fails")
        if not failed and self.child_failure_snapshot_id is not None:
            raise ValueError("child_failure_snapshot_id is forbidden when replay succeeds")
        if self.child_failure_snapshot_id is not None:
            _required("child_failure_snapshot_id", self.child_failure_snapshot_id)
            if self.child_failure_snapshot_id == self.parent_failure_snapshot_id:
                raise ValueError("child_failure_snapshot_id must differ from parent_failure_snapshot_id")
        object.__setattr__(self, "failure_classes", failure_classes)
        for name in ("adapter_changes", "metrics", "metadata"):
            _freeze_mapping(self, name)
        if self.mode is not ReplayMode.CROSS_MODEL and self.adapter_changes:
            raise ValueError("adapter_changes are only valid for CROSS_MODEL replay results")


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
            "state_hash": value.state_hash,
            "oracle_ref": value.oracle_ref,
            "expected_contract": value.expected_contract,
            "source_evidence_refs": value.source_evidence_refs,
            "forensic_asset_sha256": value.forensic_asset_sha256,
            "oracle_asset_sha256": value.oracle_asset_sha256,
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
            "failure_snapshot_id": value.failure_snapshot_id,
            "parent_failure_snapshot_id": value.parent_failure_snapshot_id,
            "parent_state_hash": value.parent_state_hash,
            "decision_id": value.decision_id,
            "hypothesis_id": value.hypothesis_id,
            "expected_causal_implication": value.expected_causal_implication,
            "mode": value.mode,
            "source_model_id": value.source_model_id,
            "source_model_digest": value.source_model_digest,
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
            "failure_snapshot_id": value.failure_snapshot_id,
            "parent_failure_snapshot_id": value.parent_failure_snapshot_id,
            "parent_state_hash": value.parent_state_hash,
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
