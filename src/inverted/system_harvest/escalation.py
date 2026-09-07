from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


REQUIRED_ESCALATION_SECTIONS = (
    "TASK_CONTRACT",
    "ORIGINAL_INSTRUCTIONS",
    "ACTIVE_INGREDIENTS",
    "MODEL_VISIBLE_CONTEXT",
    "SYSTEM_VISIBLE_STATE",
    "MODEL_RUNTIME",
    "INFERENCE_PARAMETERS",
    "TOOL_REGISTRY",
    "TOOL_TRAJECTORY",
    "MODEL_TRAJECTORY",
    "FILESYSTEM_STATE",
    "GIT_STATE",
    "PROCESS_STATE",
    "ENVIRONMENT_STATE",
    "MEMORY_STATE",
    "PLAN_STATE",
    "VERIFIER_STATE",
    "PRE_FAILURE_STATE",
    "FAILING_ACTION",
    "RAW_FAILURE_RESULT",
    "POST_FAILURE_STATE",
    "PENDING_WORK",
    "RUNTIME_TELEMETRY",
    "PROVENANCE",
    "EVENT_LINEAGE",
)


class EscalationCapsuleError(ValueError):
    pass


class SnapshotSectionStatus(str, Enum):
    CAPTURED = "CAPTURED"
    CAPTURED_REDACTED = "CAPTURED_REDACTED"
    INACCESSIBLE = "INACCESSIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class SnapshotSection:
    name: str
    status: SnapshotSectionStatus
    payload: Any
    evidence_ids: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class EscalationCapsule:
    capsule_id: str
    campaign_id: str
    system_id: str
    example_id: str
    escalation_level: int
    source_model_id: str
    failure_event_id: str
    parent_capsule_id: str | None
    resume_mode: str
    continuation_directive: str
    sections: tuple[SnapshotSection, ...]
    capsule_sha256: str


def _section_dict(section: SnapshotSection) -> dict[str, Any]:
    return {
        "name": section.name,
        "status": section.status.value,
        "payload": section.payload,
        "evidence_ids": list(section.evidence_ids),
        "reason": section.reason,
    }


def _capsule_body(*, campaign_id: str, system_id: str, example_id: str,
                  escalation_level: int, source_model_id: str, failure_event_id: str,
                  parent_capsule_id: str | None, resume_mode: str,
                  continuation_directive: str, sections: tuple[SnapshotSection, ...]) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "system_id": system_id,
        "example_id": example_id,
        "escalation_level": escalation_level,
        "source_model_id": source_model_id,
        "failure_event_id": failure_event_id,
        "parent_capsule_id": parent_capsule_id,
        "resume_mode": resume_mode,
        "continuation_directive": continuation_directive,
        "sections": [_section_dict(section) for section in sections],
    }


def _hash_body(body: dict[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_sections(sections: tuple[SnapshotSection, ...]) -> None:
    names = tuple(section.name for section in sections)
    if len(names) != len(set(names)):
        raise EscalationCapsuleError("duplicate escalation section name")
    missing = sorted(set(REQUIRED_ESCALATION_SECTIONS) - set(names))
    if missing:
        raise EscalationCapsuleError(
            "missing required escalation sections: " + ", ".join(missing)
        )
    for section in sections:
        if section.status in {SnapshotSectionStatus.CAPTURED, SnapshotSectionStatus.CAPTURED_REDACTED}:
            if not section.evidence_ids:
                raise EscalationCapsuleError(f"{section.name} captured section requires evidence lineage")
        elif section.status is SnapshotSectionStatus.INACCESSIBLE:
            if not section.reason or not section.evidence_ids:
                raise EscalationCapsuleError(
                    f"{section.name} INACCESSIBLE section requires reason and supporting evidence"
                )
        elif section.status is SnapshotSectionStatus.NOT_APPLICABLE and not section.reason:
            raise EscalationCapsuleError(
                f"{section.name} NOT_APPLICABLE section requires reason"
            )


def build_escalation_capsule(*, campaign_id: str, system_id: str, example_id: str,
                             escalation_level: int, source_model_id: str,
                             failure_event_id: str, sections: tuple[SnapshotSection, ...],
                             parent_capsule_id: str | None = None) -> EscalationCapsule:
    if escalation_level < 1:
        raise EscalationCapsuleError("escalation_level must be at least 1")
    if escalation_level > 1 and not parent_capsule_id:
        raise EscalationCapsuleError("parent_capsule_id is required for recursive escalation")
    _validate_sections(sections)
    resume_mode = "CONTINUE_FROM_FAILURE_BOUNDARY"
    continuation_directive = (
        "Continue from the captured failure boundary with the original task, instructions, "
        "ingredients, environment, and trajectory intact; do not restart unless the captured "
        "evidence proves continuation is impossible or unsafe."
    )
    body = _capsule_body(
        campaign_id=campaign_id, system_id=system_id, example_id=example_id,
        escalation_level=escalation_level, source_model_id=source_model_id,
        failure_event_id=failure_event_id, parent_capsule_id=parent_capsule_id,
        resume_mode=resume_mode, continuation_directive=continuation_directive,
        sections=sections,
    )
    digest = _hash_body(body)
    capsule_id = f"ESC-{digest[:24]}"
    return EscalationCapsule(
        capsule_id, campaign_id, system_id, example_id, escalation_level, source_model_id,
        failure_event_id, parent_capsule_id, resume_mode, continuation_directive, sections, digest,
    )

def verify_escalation_capsule(capsule: EscalationCapsule) -> bool:
    try:
        _validate_sections(capsule.sections)
    except EscalationCapsuleError:
        return False
    body = _capsule_body(
        campaign_id=capsule.campaign_id,
        system_id=capsule.system_id,
        example_id=capsule.example_id,
        escalation_level=capsule.escalation_level,
        source_model_id=capsule.source_model_id,
        failure_event_id=capsule.failure_event_id,
        parent_capsule_id=capsule.parent_capsule_id,
        resume_mode=capsule.resume_mode,
        continuation_directive=capsule.continuation_directive,
        sections=capsule.sections,
    )
    return (
        capsule.resume_mode == "CONTINUE_FROM_FAILURE_BOUNDARY"
        and capsule.capsule_id == f"ESC-{_hash_body(body)[:24]}"
        and capsule.capsule_sha256 == _hash_body(body)
    )
