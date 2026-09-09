"""Frozen scientific contracts for Stage-7 operating-surface tomography."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .core import Partition


class TomographyAxis(str, Enum):
    TOOL_AVAILABILITY = "TOOL_AVAILABILITY"
    TOOL_SELECTION = "TOOL_SELECTION"
    TOOL_ARGUMENTS = "TOOL_ARGUMENTS"
    TOOL_EXECUTION_RESULT = "TOOL_EXECUTION_RESULT"
    TOOL_RESULT_INTERPRETATION = "TOOL_RESULT_INTERPRETATION"
    VERIFIER_VISIBILITY = "VERIFIER_VISIBILITY"
    VERIFIER_FEEDBACK = "VERIFIER_FEEDBACK"
    TARGETED_RECOVERY = "TARGETED_RECOVERY"
    GENERIC_RETRY_CONTROL = "GENERIC_RETRY_CONTROL"
    SKILL_PROCEDURE = "SKILL_PROCEDURE"
    SKILL_TRIGGER = "SKILL_TRIGGER"
    ESCALATION_REFERENCE = "ESCALATION_REFERENCE"

    # Temporary source-compatibility aliases. Enum iteration exposes only the
    # corrected Stage-7 scientific vocabulary above.
    SKILL_EVIDENCE_REQUIREMENT = "SKILL_PROCEDURE"
    SKILL_VERIFICATION_RULE = "VERIFIER_VISIBILITY"
    STRONGER_MODEL_ESCALATION_CONTROL = "ESCALATION_REFERENCE"


class TomographyDisposition(str, Enum):
    TOOL_REQUIRED = "TOOL_REQUIRED"
    TOOL_SELECTION_DEFICIT = "TOOL_SELECTION_DEFICIT"
    TOOL_ARGUMENT_DEFICIT = "TOOL_ARGUMENT_DEFICIT"
    TOOL_EXECUTION_FAILURE = "TOOL_EXECUTION_FAILURE"
    TOOL_INTERPRETATION_DEFICIT = "TOOL_INTERPRETATION_DEFICIT"
    VERIFIER_SUFFICIENT = "VERIFIER_SUFFICIENT"
    RECOVERY_SUFFICIENT = "RECOVERY_SUFFICIENT"
    SKILL_CANDIDATE = "SKILL_CANDIDATE"
    MODEL_INTERNAL_RESIDUAL = "MODEL_INTERNAL_RESIDUAL"
    ESCALATION_CANDIDATE = "ESCALATION_CANDIDATE"
    SAFE_STOP_BOUNDARY = "SAFE_STOP_BOUNDARY"
    UNRESOLVED = "UNRESOLVED"

    # Temporary source-compatibility aliases. Generic retry is evidence of a
    # confound, not a deployment disposition, so its old label resolves to
    # UNRESOLVED rather than creating a second scientific conclusion.
    VERIFIER_RECOVERABLE = "VERIFIER_SUFFICIENT"
    RECOVERY_POLICY_DEFICIT = "RECOVERY_SUFFICIENT"
    SKILL_DEFICIT = "SKILL_CANDIDATE"
    NONSPECIFIC_RETRY_EFFECT = "UNRESOLVED"


class TomographyStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    ANALYZED = "ANALYZED"
    STOPPED = "STOPPED"


class TomographyStopReason(str, Enum):
    NO_ELIGIBLE_RESIDUALS = "NO_ELIGIBLE_RESIDUALS"
    DECISION_ALREADY_RESOLVED = "DECISION_ALREADY_RESOLVED"
    NO_DIAGNOSTIC_CONTRAST = "NO_DIAGNOSTIC_CONTRAST"
    INSUFFICIENT_OBSERVABLE_EVIDENCE = "INSUFFICIENT_OBSERVABLE_EVIDENCE"
    CALL_CEILING_REACHED = "CALL_CEILING_REACHED"
    PROTECTED_NEGATIVE_TRANSFER = "PROTECTED_NEGATIVE_TRANSFER"
    MODEL_INTERNAL_BOUNDARY = "MODEL_INTERNAL_BOUNDARY"
    INVALID_STUDY = "INVALID_STUDY"


def _required(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


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


def _enum_tuple(name: str, values: tuple[Any, ...], enum_type: type[Enum], *, allow_empty: bool = False):
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence")
    result = tuple(item if isinstance(item, enum_type) else enum_type(item) for item in values)
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must be unique")
    return result


def stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:24]}"


@dataclass(frozen=True)
class TomographyPolicy:
    """Bounded Stage-7 planning policy; never grants execution or certification."""

    max_new_probes: int = 3
    max_generic_retry_controls: int = 1
    stage456_feedback_required: bool = True
    certification_allowed: bool = False

    def __post_init__(self) -> None:
        for name in ("max_new_probes", "max_generic_retry_controls"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_new_probes < 1:
            raise ValueError("max_new_probes must be at least 1")
        if self.max_generic_retry_controls > 1:
            raise ValueError("Stage 7 permits at most one matched generic-retry control")
        if type(self.stage456_feedback_required) is not bool:
            raise TypeError("stage456_feedback_required must be boolean")
        if type(self.certification_allowed) is not bool:
            raise TypeError("certification_allowed must be boolean")
        if self.certification_allowed:
            raise ValueError("Stage 7 cannot certify")


@dataclass(frozen=True)
class TomographyStudy:
    study_id: str
    failure_snapshot_id: str
    parent_state_hash: str
    partition: Partition
    decision_ids: tuple[str, ...]
    candidate_axes: tuple[TomographyAxis, ...]
    baseline_evidence_refs: tuple[str, ...]
    probe_ids: tuple[str, ...]
    max_new_probes: int
    projected_calls: int
    status: TomographyStatus
    stop_reason: TomographyStopReason | None = None

    def __post_init__(self) -> None:
        _required("study_id", self.study_id)
        _required("failure_snapshot_id", self.failure_snapshot_id)
        if not isinstance(self.parent_state_hash, str) or len(self.parent_state_hash) != 64:
            raise ValueError("parent_state_hash must be a SHA-256 digest")
        object.__setattr__(self, "partition", self.partition if isinstance(self.partition, Partition) else Partition(self.partition))
        object.__setattr__(self, "decision_ids", _strings("decision_ids", self.decision_ids))
        object.__setattr__(self, "candidate_axes", _enum_tuple("candidate_axes", self.candidate_axes, TomographyAxis, allow_empty=True))
        object.__setattr__(self, "baseline_evidence_refs", _strings("baseline_evidence_refs", self.baseline_evidence_refs))
        object.__setattr__(self, "probe_ids", _strings("probe_ids", self.probe_ids, allow_empty=True))
        object.__setattr__(self, "status", self.status if isinstance(self.status, TomographyStatus) else TomographyStatus(self.status))
        if self.stop_reason is not None and not isinstance(self.stop_reason, TomographyStopReason):
            object.__setattr__(self, "stop_reason", TomographyStopReason(self.stop_reason))
        for name in ("max_new_probes", "projected_calls"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_new_probes < 1:
            raise ValueError("max_new_probes must be at least 1")
        if len(self.probe_ids) > self.max_new_probes:
            raise ValueError("probe_ids exceed max_new_probes")
        if self.status is TomographyStatus.STOPPED and self.stop_reason is None:
            raise ValueError("stopped study requires stop_reason")
        if self.status is not TomographyStatus.STOPPED and self.stop_reason is not None:
            raise ValueError("non-stopped study cannot have stop_reason")
        if self.status is TomographyStatus.STOPPED and self.probe_ids:
            raise ValueError("stopped study cannot contain executable probes")

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": "TOMOGRAPHY_STUDY",
            "study_id": self.study_id,
            "failure_snapshot_id": self.failure_snapshot_id,
            "parent_state_hash": self.parent_state_hash,
            "partition": self.partition.value,
            "decision_ids": list(self.decision_ids),
            "candidate_axes": [item.value for item in self.candidate_axes],
            "baseline_evidence_refs": list(self.baseline_evidence_refs),
            "probe_ids": list(self.probe_ids),
            "max_new_probes": self.max_new_probes,
            "projected_calls": self.projected_calls,
            "status": self.status.value,
            "stop_reason": None if self.stop_reason is None else self.stop_reason.value,
        }


@dataclass(frozen=True)
class TomographyProbeSpec:
    probe_id: str
    study_id: str
    axis: TomographyAxis
    intervention_id: str
    control_intervention_id: str | None
    changed_dimensions: tuple[str, ...]
    expected_implication: str
    projected_calls: int
    protected: bool

    def __post_init__(self) -> None:
        for name in ("probe_id", "study_id", "intervention_id", "expected_implication"):
            _required(name, getattr(self, name))
        object.__setattr__(self, "axis", self.axis if isinstance(self.axis, TomographyAxis) else TomographyAxis(self.axis))
        object.__setattr__(self, "changed_dimensions", _strings("changed_dimensions", self.changed_dimensions))
        if self.control_intervention_id is not None:
            _required("control_intervention_id", self.control_intervention_id)
        if not isinstance(self.projected_calls, int) or isinstance(self.projected_calls, bool) or self.projected_calls < 1:
            raise ValueError("projected_calls must be a positive integer")
        if type(self.protected) is not bool:
            raise TypeError("protected must be boolean")

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": "TOMOGRAPHY_PROBE",
            "probe_id": self.probe_id,
            "study_id": self.study_id,
            "axis": self.axis.value,
            "intervention_id": self.intervention_id,
            "control_intervention_id": self.control_intervention_id,
            "changed_dimensions": list(self.changed_dimensions),
            "expected_implication": self.expected_implication,
            "projected_calls": self.projected_calls,
            "protected": self.protected,
        }


# Backwards-compatible source alias; the scientific public name is ProbeSpec.
TomographyProbe = TomographyProbeSpec


@dataclass(frozen=True)
class TomographyOutcome:
    outcome_id: str
    study_id: str
    probe_id: str
    replay_result_id: str
    semantic_success: bool
    contract_valid: bool
    score: float
    first_divergence: str | None
    comparison_refs: tuple[str, ...]
    protected_regression: bool
    child_failure_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("outcome_id", "study_id", "probe_id", "replay_result_id"):
            _required(name, getattr(self, name))
        for name in ("semantic_success", "contract_valid", "protected_regression"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool) or not math.isfinite(float(self.score)):
            raise TypeError("score must be finite numeric")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "comparison_refs", _strings("comparison_refs", self.comparison_refs))
        if self.first_divergence is not None:
            _required("first_divergence", self.first_divergence)
        if self.child_failure_snapshot_id is not None:
            _required("child_failure_snapshot_id", self.child_failure_snapshot_id)

    @property
    def success(self) -> bool:
        return self.semantic_success and self.contract_valid

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": "TOMOGRAPHY_OUTCOME",
            "outcome_id": self.outcome_id,
            "study_id": self.study_id,
            "probe_id": self.probe_id,
            "replay_result_id": self.replay_result_id,
            "semantic_success": self.semantic_success,
            "contract_valid": self.contract_valid,
            "score": self.score,
            "first_divergence": self.first_divergence,
            "comparison_refs": list(self.comparison_refs),
            "protected_regression": self.protected_regression,
            "child_failure_snapshot_id": self.child_failure_snapshot_id,
        }


@dataclass(frozen=True)
class TomographyAssessment:
    profile_id: str
    study_id: str
    dispositions: tuple[TomographyDisposition, ...]
    supported_hypotheses: tuple[str, ...]
    falsified_hypotheses: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    next_decisions: tuple[str, ...]
    route_back_stage: str | None
    model_internal_boundary: bool
    promotion_allowed: bool
    certification_allowed: bool = False
    stop_reason: TomographyStopReason | None = None

    def __post_init__(self) -> None:
        _required("profile_id", self.profile_id)
        _required("study_id", self.study_id)
        object.__setattr__(self, "dispositions", _enum_tuple("dispositions", self.dispositions, TomographyDisposition))
        for name in ("supported_hypotheses", "falsified_hypotheses"):
            object.__setattr__(self, name, _strings(name, getattr(self, name), allow_empty=True))
        object.__setattr__(self, "evidence_refs", _strings("evidence_refs", self.evidence_refs))
        object.__setattr__(self, "next_decisions", _strings("next_decisions", self.next_decisions))
        if self.route_back_stage is not None:
            _required("route_back_stage", self.route_back_stage)
        for name in ("model_internal_boundary", "promotion_allowed", "certification_allowed"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        if self.certification_allowed:
            raise ValueError("Stage 7 cannot certify")
        if self.promotion_allowed and self.route_back_stage != "stage4":
            raise ValueError("Stage-7 movement must route back to stage4")
        if self.model_internal_boundary and TomographyDisposition.MODEL_INTERNAL_RESIDUAL not in self.dispositions:
            raise ValueError("model_internal_boundary requires MODEL_INTERNAL_RESIDUAL")
        if self.stop_reason is not None and not isinstance(self.stop_reason, TomographyStopReason):
            object.__setattr__(self, "stop_reason", TomographyStopReason(self.stop_reason))
        if self.stop_reason is TomographyStopReason.PROTECTED_NEGATIVE_TRANSFER and self.promotion_allowed:
            raise ValueError("protected negative transfer vetoes promotion")

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": "TOMOGRAPHY_PROFILE",
            "profile_id": self.profile_id,
            "study_id": self.study_id,
            "dispositions": [item.value for item in self.dispositions],
            "supported_hypotheses": list(self.supported_hypotheses),
            "falsified_hypotheses": list(self.falsified_hypotheses),
            "evidence_refs": list(self.evidence_refs),
            "next_decisions": list(self.next_decisions),
            "route_back_stage": self.route_back_stage,
            "model_internal_boundary": self.model_internal_boundary,
            "promotion_allowed": self.promotion_allowed,
            "certification_allowed": False,
            "stop_reason": None if self.stop_reason is None else self.stop_reason.value,
        }


# Backwards-compatible source alias; storage migration is handled independently.
TomographyProfile = TomographyAssessment
