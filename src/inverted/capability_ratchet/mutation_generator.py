"""Deterministic, template-bound Stage-6 mutation generation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .core import FailureFixture, MutationFixture, Partition
from .mutation_core import MutationAxis, MutationOrigin, MutationSpec
from .replay_store import ReplayStore


_PROVENANCE_KEYS = frozenset(
    {
        "source_model_id",
        "source_model_digest",
        "source_runtime",
        "inference_profile",
        "partition",
        "state_hash",
        "source_state_hash",
        "source_failure_snapshot_id",
        "failure_snapshot_id",
        "record_id",
        "record_type",
    }
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mutation template mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("mutation template numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported mutation template value: {type(value).__name__}")


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("mutation template numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported mutation template value: {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def semantic_contract_hash(contract: Any) -> str:
    """Hash a semantic contract independent of mapping insertion order."""

    return hashlib.sha256(_canonical_bytes(contract)).hexdigest()


def _required(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _contains_provenance_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _PROVENANCE_KEYS:
                return True
            if _contains_provenance_key(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_provenance_key(item) for item in value)
    return False


def _normalize_path(value: Any, *, name: str) -> tuple[str | int, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be an explicit path sequence")
    path = tuple(value)
    if not path:
        raise ValueError(f"{name} must not be empty")
    for part in path:
        if not isinstance(part, (str, int)) or isinstance(part, bool):
            raise ValueError(f"{name} may contain only string keys or integer indexes")
    return path


def _set_path(payload: Any, path: Sequence[str | int], value: Any) -> None:
    current = payload
    for part in path[:-1]:
        try:
            current = current[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"mutation path does not exist: {list(path)!r}") from exc
    leaf = path[-1]
    try:
        if isinstance(current, list):
            if not isinstance(leaf, int) or isinstance(leaf, bool):
                raise TypeError
            current[leaf] = copy.deepcopy(_plain(value))
        elif isinstance(current, dict):
            if not isinstance(leaf, str):
                raise TypeError
            if leaf not in current:
                raise KeyError(leaf)
            current[leaf] = copy.deepcopy(_plain(value))
        else:
            raise TypeError
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"mutation path does not exist: {list(path)!r}") from exc


@dataclass(frozen=True)
class MutationTemplate:
    source_failure_snapshot_id: str
    structural_region_id: str
    semantic_contract: Any
    model_visible_template: Any
    oracle_template: Any
    allowed_axes: tuple[MutationAxis, ...]
    operator_state: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required("source_failure_snapshot_id", self.source_failure_snapshot_id)
        _required("structural_region_id", self.structural_region_id)
        if isinstance(self.allowed_axes, (str, bytes, bytearray)) or not isinstance(
            self.allowed_axes, (list, tuple)
        ):
            raise TypeError("allowed_axes must be a sequence of MutationAxis values")
        axes = tuple(
            axis if isinstance(axis, MutationAxis) else MutationAxis(axis)
            for axis in self.allowed_axes
        )
        if not axes:
            raise ValueError("allowed_axes must not be empty")
        if len(set(axes)) != len(axes):
            raise ValueError("allowed_axes must be unique")
        object.__setattr__(self, "allowed_axes", axes)
        for name in (
            "semantic_contract",
            "model_visible_template",
            "oracle_template",
            "operator_state",
            "metadata",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        if not isinstance(self.operator_state, Mapping):
            raise TypeError("operator_state must be a mapping")
        mechanism_id = self.operator_state.get("mechanism_id")
        if not isinstance(mechanism_id, str) or not mechanism_id.strip():
            raise ValueError("operator_state.mechanism_id is required")
        for axis in axes:
            config = self.operator_state.get(axis.value)
            if not isinstance(config, Mapping):
                raise ValueError(f"operator_state is missing {axis.value} configuration")
            _normalize_path(config.get("visible_path"), name=f"{axis.value}.visible_path")
            if config.get("requires_oracle"):
                _normalize_path(config.get("oracle_path"), name=f"{axis.value}.oracle_path")


class MutationGenerator:
    """Generate canonical mutation fixtures from explicit structured templates."""

    def __init__(self, replay_store: ReplayStore) -> None:
        self.replay_store = replay_store

    def _root(self, source: FailureFixture) -> FailureFixture:
        current = source
        seen: set[str] = set()
        while current.parent_failure_snapshot_id is not None:
            if current.failure_snapshot_id in seen:
                raise ValueError("source failure lineage contains a cycle")
            seen.add(current.failure_snapshot_id)
            current = self.replay_store.get_failure(current.parent_failure_snapshot_id)
        return current

    def generate(self, template: MutationTemplate, spec: MutationSpec) -> MutationFixture:
        source = self.replay_store.get_failure(template.source_failure_snapshot_id)
        if source.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH and SEALED fixtures cannot be synthetically mutated")
        if spec.axis not in template.allowed_axes:
            raise ValueError(f"mutation axis {spec.axis.value} is not authorized by template")
        if spec.structural_region_id != template.structural_region_id:
            raise ValueError("mutation structural region does not match template")
        if _contains_provenance_key(spec.value):
            raise ValueError("mutation may not change model/runtime provenance")

        config = template.operator_state.get(spec.axis.value)
        if not isinstance(config, Mapping):
            raise ValueError(f"template has no operator for {spec.axis.value}")
        visible_path = _normalize_path(
            config.get("visible_path"), name=f"{spec.axis.value}.visible_path"
        )
        requires_oracle = bool(config.get("requires_oracle", False))

        visible = copy.deepcopy(_plain(template.model_visible_template))
        oracle = copy.deepcopy(_plain(template.oracle_template))

        if requires_oracle:
            if not isinstance(spec.value, Mapping) or "visible" not in spec.value or "oracle" not in spec.value:
                raise ValueError("semantic mutation requires deterministic visible and oracle values")
            if "semantic_contract" in spec.value:
                raise ValueError("semantic contract changes require a registered contract transformer")
            _set_path(visible, visible_path, spec.value["visible"])
            oracle_path = _normalize_path(
                config.get("oracle_path"), name=f"{spec.axis.value}.oracle_path"
            )
            _set_path(oracle, oracle_path, spec.value["oracle"])
        else:
            if isinstance(spec.value, Mapping) and "semantic_contract" in spec.value:
                raise ValueError("semantic contract changes require deterministic oracle/contract transforms")
            _set_path(visible, visible_path, spec.value)

        visible_sha = self.replay_store.put_asset(visible)
        oracle_sha = self.replay_store.put_asset(oracle)
        root = self._root(source)
        mechanism_id = str(template.operator_state["mechanism_id"])
        metadata = _plain(template.metadata)
        if not isinstance(metadata, dict):
            raise TypeError("mutation template metadata must materialize as a mapping")
        metadata.update({
            "mutation_spec_id": spec.spec_id,
            "decision_id": spec.decision_id,
            "protected": spec.protected,
        })
        fixture = MutationFixture.create(
            failure_snapshot_id=root.failure_snapshot_id,
            source_failure_snapshot_id=source.failure_snapshot_id,
            source_state_hash=source.state_hash,
            mechanism_id=mechanism_id,
            mutation_axis=spec.axis,
            mutation_direction=spec.direction,
            mutation_value=spec.value,
            structural_region_id=spec.structural_region_id,
            model_visible_asset_sha256=visible_sha,
            oracle_asset_sha256=oracle_sha,
            semantic_contract_hash=semantic_contract_hash(template.semantic_contract),
            partition=source.partition,
            origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
            metadata=metadata,
        )
        record_id = self.replay_store.append(fixture)
        return replace(fixture, record_id=record_id)

    def generate_many(
        self, template: MutationTemplate, specs: Sequence[MutationSpec]
    ) -> tuple[MutationFixture, ...]:
        items = tuple(specs)
        ids = tuple(spec.spec_id for spec in items)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate mutation specs are forbidden in one schedule")
        return tuple(self.generate(template, spec) for spec in items)