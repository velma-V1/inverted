from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TemplateValidationError(ValueError):
    pass


class CoverageStatus(str, Enum):
    PENDING = "PENDING"
    CAPTURED = "CAPTURED"
    CAPTURED_PARTIAL = "CAPTURED_PARTIAL"
    INACCESSIBLE = "INACCESSIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONTRADICTED = "CONTRADICTED"
    NEEDS_RUNTIME_PROBE = "NEEDS_RUNTIME_PROBE"
    NEEDS_STATIC_PROBE = "NEEDS_STATIC_PROBE"
    NEEDS_GAP_CLOSURE = "NEEDS_GAP_CLOSURE"


@dataclass(frozen=True)
class EscalationPolicy:
    trigger_on: tuple[str, ...]
    resume_mode: str
    recursive: bool
    snapshot_before_recovery_mutation: bool
    required_snapshot_sections: tuple[str, ...]


@dataclass(frozen=True)
class HarvestTemplate:
    schema_version: int
    campaign_id: str
    systems: tuple[str, ...]
    evidence_layers: tuple[str, ...]
    coverage_domains: tuple[str, ...]
    behavioral_battery: tuple[str, ...]
    perturbation_battery: tuple[str, ...]
    required_evidence_channels: tuple[str, ...]
    one_pass_evidence_standard: bool
    escalation_policy: EscalationPolicy
    require_all_systems: bool
    require_future_query_probe: bool
    require_verified_manifests: bool
    forbid_partial_completion: bool
