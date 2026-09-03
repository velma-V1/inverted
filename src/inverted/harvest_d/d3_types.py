from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import uuid

from .d3_config import D3Phase
from .types import stable_hash


class MissingnessReason(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EXPOSED_BY_RUNTIME = "NOT_EXPOSED_BY_RUNTIME"
    COLLECTION_FAILED = "COLLECTION_FAILED"
    COLLECTION_SKIPPED_TO_AVOID_PERTURBATION = "COLLECTION_SKIPPED_TO_AVOID_PERTURBATION"
    REDACTED_FOR_SAFETY_SECRET_PROTECTION = "REDACTED_FOR_SAFETY/SECRET_PROTECTION"
    UNKNOWN = "UNKNOWN"
    CAPTURE_INCOMPLETE = "CAPTURE_INCOMPLETE"
    NOT_PREVIOUSLY_COLLECTED = "NOT_PREVIOUSLY_COLLECTED"


class EvidenceAdmissibility(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    SEGMENTED = "SEGMENTED"
    REJECTED = "REJECTED"


class RecoveryChoice(str, Enum):
    RETRY = "RETRY"
    ALTERNATE_ACTION = "ALTERNATE_ACTION"
    RECONCILE = "RECONCILE"
    ROLLBACK = "ROLLBACK"
    COMPENSATE = "COMPENSATE"
    REPLAN = "REPLAN"
    DECOMPOSE = "DECOMPOSE"
    ACQUIRE_EVIDENCE = "ACQUIRE_EVIDENCE"
    ESCALATE = "ESCALATE"
    SAFE_STOP = "SAFE_STOP"


class RecoveryStage(str, Enum):
    DETECTION = "DETECTION"
    DIAGNOSIS = "DIAGNOSIS"
    SELECTION = "SELECTION"
    ADMISSION = "ADMISSION"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"


@dataclass(frozen=True)
class D3Condition:
    condition_id: str
    phase: D3Phase
    arm_kind: str
    evidence_partition: str


@dataclass(frozen=True)
class InformationField:
    field_id: str
    value: Any
    source_type: str
    trust_class: str
    model_visible: bool
    reason: str = ""
    transform_chain: tuple[str, ...] = ()
    extras: dict[str, Any] | None = None


@dataclass(frozen=True)
class InformationPacket:
    packet_id: str
    fields: tuple[InformationField, ...]
    rendered: str
    representation: str
    timing: str
    ordering: str = "DEFAULT"
    amount: str = "UNSPECIFIED"
    placement: str = "TASK_CONTEXT"
    control_kind: str = "TARGET"
    base_semantic_field_hash: str | None = None
    approx_token_count: int = 0

    @property
    def model_visible_field_ids(self) -> tuple[str, ...]:
        return tuple(field.field_id for field in self.fields if field.model_visible)

    @property
    def semantic_field_hash(self) -> str:
        return stable_hash(
            [(field.field_id, field.value) for field in self.fields if field.model_visible]
        )


@dataclass(frozen=True)
class AssistanceCondition:
    mechanism_id: str
    mode: str
    reason: str = ""


@dataclass(frozen=True)
class CallCaptureStatus:
    physical_model_call_id: str
    required_present: bool
    missing_required: tuple[str, ...] = ()

    @property
    def admissibility(self) -> EvidenceAdmissibility:
        if self.required_present and not self.missing_required:
            return EvidenceAdmissibility.ADMISSIBLE
        return EvidenceAdmissibility.DIAGNOSTIC_ONLY


@dataclass(frozen=True)
class D3Event:
    run_id: str
    experiment_id: str
    case_id: str
    arm_id: str
    event_id: str
    parent_event_id: str | None
    sequence: int
    timestamp: str
    component: str
    event_type: str
    pre_state_hash: str
    post_state_hash: str | None
    model_visible_information_hash: str
    system_known_information_hash: str
    authority_scope_hash: str
    evidence_set_hash: str
    proposed_action: str | None = None
    proposed_disposition: str | None = None
    admitted_action: str | None = None
    admission_reason: str | None = None
    recovery_decision: str | None = None
    recovery_reason: str | None = None
    verifier_result: str | None = None
    effect_status: str | None = None
    physical_model_call_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    runtime_provenance_hash: str | None = None
    hard_invariant_status: str = "PASS"
    semantic_oracle_result: bool | None = None
    artifact_refs: tuple[str, ...] = ()
    extras: dict[str, Any] | None = None

    @classmethod
    def for_test(cls, *, model_visible: object, system_known: object) -> "D3Event":
        return cls(
            run_id="test-run",
            experiment_id="test-experiment",
            case_id="test-case",
            arm_id="test-arm",
            event_id=f"event-{uuid.uuid4().hex}",
            parent_event_id=None,
            sequence=1,
            timestamp="1970-01-01T00:00:00Z",
            component="test",
            event_type="TEST",
            pre_state_hash=stable_hash({}),
            post_state_hash=None,
            model_visible_information_hash=stable_hash(model_visible),
            system_known_information_hash=stable_hash(system_known),
            authority_scope_hash=stable_hash({}),
            evidence_set_hash=stable_hash({}),
        )


@dataclass(frozen=True)
class RecoveryTrajectory:
    trajectory_id: str
    case_id: str
    stages: tuple[tuple[RecoveryStage, str], ...]
    final_state: str

    def stage_value(self, stage: RecoveryStage) -> str | None:
        for current, value in self.stages:
            if current is stage:
                return value
        return None

    @property
    def migrated(self) -> bool:
        return self.final_state == "MIGRATED"


@dataclass(frozen=True)
class ProtocolViolation:
    violation_id: str
    observed_deviation: str
    affected_ids: tuple[str, ...]
    admissibility: str
    intended_protocol: str = ""
    cause: str = ""


@dataclass(frozen=True)
class AssumptionRecord:
    assumption_id: str
    version: int
    statement: str
    state: str
    evidence_ids: tuple[str, ...] = ()
