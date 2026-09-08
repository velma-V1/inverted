"""Frozen scientific contracts for V3 causal failure research."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class DivergenceClass(str, Enum):
    INSUFFICIENT_REASONING = "INSUFFICIENT_REASONING"
    REASONING_DRIFT = "REASONING_DRIFT"
    MISSING_STATE = "MISSING_STATE"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    EVIDENCE_FAILURE = "EVIDENCE_FAILURE"
    AUTHORITY_SCOPE = "AUTHORITY_SCOPE"
    AMBIGUITY = "AMBIGUITY"
    ACTION_SPACE = "ACTION_SPACE"
    CONTEXT_PRESSURE = "CONTEXT_PRESSURE"
    CONTRACT_INTERFACE = "CONTRACT_INTERFACE"
    DETERMINISTIC_COMPUTATION = "DETERMINISTIC_COMPUTATION"
    TOOL_CAPABILITY = "TOOL_CAPABILITY"
    TOOL_SELECTION = "TOOL_SELECTION"
    TOOL_ARGUMENTS = "TOOL_ARGUMENTS"
    TOOL_INTERPRETATION = "TOOL_INTERPRETATION"
    VERIFIER_FEEDBACK = "VERIFIER_FEEDBACK"
    RECOVERY_POLICY = "RECOVERY_POLICY"
    SKILL_DEFICIT = "SKILL_DEFICIT"
    MODEL_CAPABILITY_LIMIT = "MODEL_CAPABILITY_LIMIT"
    UNKNOWN_NOVEL = "UNKNOWN_NOVEL"


class ArchitectureOwner(str, Enum):
    MODEL = "MODEL"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"
    SKILL = "SKILL"
    VERIFIER = "VERIFIER"
    RECOVERY = "RECOVERY"
    ROUTER = "ROUTER"
    FINE_TUNE = "FINE_TUNE"
    ESCALATION = "ESCALATION"
    SAFE_STOP = "SAFE_STOP"


def _required(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _string_tuple(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of strings")
    result = tuple(values)
    if not result or any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{name} must contain non-blank strings")
    return result


@dataclass(frozen=True)
class FirstDivergence:
    divergence_class: DivergenceClass
    observable_path: str
    event_index: int
    evidence_refs: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.divergence_class, DivergenceClass):
            object.__setattr__(self, "divergence_class", DivergenceClass(self.divergence_class))
        _required("observable_path", self.observable_path)
        if not isinstance(self.event_index, int) or isinstance(self.event_index, bool) or self.event_index < 0:
            raise ValueError("event_index must be a non-negative integer")
        object.__setattr__(self, "evidence_refs", _string_tuple("evidence_refs", self.evidence_refs))
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise TypeError("confidence must be numeric")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", float(self.confidence))


class HypothesisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class CausalHypothesis:
    hypothesis_id: str
    failure_snapshot_id: str
    parent_state_hash: str
    divergence: FirstDivergence
    owner_candidate: ArchitectureOwner
    claim: str
    expected_if_true: str
    falsifier: str
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    protected_exploration: bool = False

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "failure_snapshot_id", "claim", "expected_if_true", "falsifier"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        if not isinstance(self.divergence, FirstDivergence):
            raise TypeError("divergence must be FirstDivergence")
        if not isinstance(self.owner_candidate, ArchitectureOwner):
            object.__setattr__(self, "owner_candidate", ArchitectureOwner(self.owner_candidate))
        if not isinstance(self.status, HypothesisStatus):
            object.__setattr__(self, "status", HypothesisStatus(self.status))
        if type(self.protected_exploration) is not bool:
            raise TypeError("protected_exploration must be boolean")

    @classmethod
    def create(
        cls,
        *,
        failure_snapshot_id: str,
        parent_state_hash: str,
        divergence: FirstDivergence,
        owner_candidate: ArchitectureOwner,
        claim: str,
        expected_if_true: str,
        falsifier: str,
        status: HypothesisStatus = HypothesisStatus.ACTIVE,
        protected_exploration: bool = False,
    ) -> "CausalHypothesis":
        payload = {
            "failure_snapshot_id": failure_snapshot_id,
            "parent_state_hash": parent_state_hash,
            "divergence_class": divergence.divergence_class.value,
            "observable_path": divergence.observable_path,
            "event_index": divergence.event_index,
            "evidence_refs": list(divergence.evidence_refs),
            "confidence": divergence.confidence,
            "owner_candidate": ArchitectureOwner(owner_candidate).value,
            "claim": claim,
            "expected_if_true": expected_if_true,
            "falsifier": falsifier,
            "status": HypothesisStatus(status).value,
            "protected_exploration": protected_exploration,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return cls(
            hypothesis_id=f"hyp-{digest[:24]}",
            failure_snapshot_id=failure_snapshot_id,
            parent_state_hash=parent_state_hash,
            divergence=divergence,
            owner_candidate=owner_candidate,
            claim=claim,
            expected_if_true=expected_if_true,
            falsifier=falsifier,
            status=status,
            protected_exploration=protected_exploration,
        )

class InterventionKind(str, Enum):
    PROMPT = "PROMPT"
    CONTEXT = "CONTEXT"
    REPRESENTATION = "REPRESENTATION"
    DELIVERY = "DELIVERY"
    COGNITION = "COGNITION"
    DETERMINISTIC = "DETERMINISTIC"
    TOOL = "TOOL"
    SKILL = "SKILL"
    VERIFICATION_RECOVERY = "VERIFICATION_RECOVERY"
    ESCALATION = "ESCALATION"
    SHAM = "SHAM"
    ABLATION = "ABLATION"


class MechanismRole(str, Enum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    ENABLER = "ENABLER"
    SYNERGIST = "SYNERGIST"
    SUPPRESSOR = "SUPPRESSOR"
    REPLACEMENT = "REPLACEMENT"
    RECURRENT = "RECURRENT"
    REANCHOR = "REANCHOR"
    RECOVERY_ONLY = "RECOVERY_ONLY"
    REDUNDANT = "REDUNDANT"
    HARMFUL = "HARMFUL"
    UNRESOLVED = "UNRESOLVED"


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value):
            raise TypeError("causal mapping keys must be non-blank strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("causal payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"causal payload contains unsupported value: {type(value).__name__}")


def _freeze_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return frozen


@dataclass(frozen=True)
class InterventionDefinition:
    intervention_id: str
    hypothesis_id: str
    failure_snapshot_id: str
    parent_state_hash: str
    kind: InterventionKind
    label: str
    changed_dimensions: tuple[str, ...] = ()
    overrides: Mapping[str, Any] = field(default_factory=dict)
    expected_causal_implication: str = ""
    projected_physical_calls: int = 1
    composition: tuple[str, ...] = ()
    sham_for: str | None = None
    ablates: tuple[str, ...] = ()
    protected_exploration: bool = False

    def __post_init__(self) -> None:
        for name in ("intervention_id", "hypothesis_id", "failure_snapshot_id", "label", "expected_causal_implication"):
            _required(name, getattr(self, name))
        _sha256("parent_state_hash", self.parent_state_hash)
        if not isinstance(self.kind, InterventionKind):
            object.__setattr__(self, "kind", InterventionKind(self.kind))
        dimensions = tuple(self.changed_dimensions)
        if any(not isinstance(item, str) or not item for item in dimensions):
            raise ValueError("changed_dimensions must contain non-blank strings")
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("changed_dimensions must be unique")
        overrides = _freeze_mapping("overrides", self.overrides)
        if set(overrides) != set(dimensions):
            raise ValueError("overrides must exactly match changed_dimensions")
        object.__setattr__(self, "changed_dimensions", dimensions)
        object.__setattr__(self, "overrides", overrides)
        object.__setattr__(self, "composition", tuple(self.composition))
        object.__setattr__(self, "ablates", tuple(self.ablates))
        if not isinstance(self.projected_physical_calls, int) or isinstance(self.projected_physical_calls, bool) or self.projected_physical_calls < 0:
            raise ValueError("projected_physical_calls must be a non-negative integer")
        if self.kind is InterventionKind.SHAM and not self.sham_for:
            raise ValueError("SHAM intervention requires sham_for")
        if self.kind is InterventionKind.ABLATION and not self.ablates:
            raise ValueError("ABLATION intervention requires ablates")
        if self.kind is InterventionKind.DETERMINISTIC and self.projected_physical_calls != 0:
            raise ValueError("DETERMINISTIC intervention must project zero model calls")

    @classmethod
    def create(
        cls,
        *,
        hypothesis_id: str,
        failure_snapshot_id: str,
        parent_state_hash: str,
        kind: InterventionKind,
        label: str,
        changed_dimensions: tuple[str, ...] = (),
        overrides: Mapping[str, Any] | None = None,
        expected_causal_implication: str,
        projected_physical_calls: int = 1,
        composition: tuple[str, ...] = (),
        sham_for: str | None = None,
        ablates: tuple[str, ...] = (),
        protected_exploration: bool = False,
    ) -> "InterventionDefinition":
        raw_overrides = {} if overrides is None else dict(overrides)
        payload = {
            "hypothesis_id": hypothesis_id,
            "failure_snapshot_id": failure_snapshot_id,
            "parent_state_hash": parent_state_hash,
            "kind": InterventionKind(kind).value,
            "label": label,
            "changed_dimensions": list(changed_dimensions),
            "overrides": raw_overrides,
            "expected_causal_implication": expected_causal_implication,
            "projected_physical_calls": projected_physical_calls,
            "composition": list(composition),
            "sham_for": sham_for,
            "ablates": list(ablates),
            "protected_exploration": protected_exploration,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return cls(
            intervention_id=f"int-{digest[:24]}",
            hypothesis_id=hypothesis_id,
            failure_snapshot_id=failure_snapshot_id,
            parent_state_hash=parent_state_hash,
            kind=kind,
            label=label,
            changed_dimensions=changed_dimensions,
            overrides=raw_overrides,
            expected_causal_implication=expected_causal_implication,
            projected_physical_calls=projected_physical_calls,
            composition=composition,
            sham_for=sham_for,
            ablates=ablates,
            protected_exploration=protected_exploration,
        )
