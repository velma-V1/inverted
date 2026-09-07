from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TemplateValidationError(ValueError):
    pass


class ResponsibilityOwner(str, Enum):
    KERNEL = "KERNEL"
    SYSTEM = "SYSTEM"
    MODEL = "MODEL"
    HYBRID = "HYBRID"
    VERIFIER = "VERIFIER"
    RECOVERY = "RECOVERY"
    HUMAN = "HUMAN"


class Disposition(str, Enum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    REDUNDANT = "REDUNDANT"
    HARMFUL = "HARMFUL"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class MechanismSpec:
    mechanism_id: str
    decision_id: str
    description: str
    owner: ResponsibilityOwner
    responsibilities: tuple[str, ...]
    expected_role: str
    isolation_required: bool
    ablation_required: bool

@dataclass(frozen=True)
class InteractionProbe:
    probe_id: str
    members: tuple[str, ...]
    decision_id: str
    reason: str


@dataclass(frozen=True)
class SystemTestTemplate:
    schema_version: int
    template_id: str
    system_id: str
    decision_id: str
    description: str
    factors: tuple[str, ...]
    mechanisms: tuple[MechanismSpec, ...]
    interactions: tuple[InteractionProbe, ...]
    task_families: tuple[str, ...]
    operating_regions: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    hard_gates: tuple[str, ...]
    evidence_fields: tuple[str, ...]
    allowed_dispositions: tuple[Disposition, ...]

    @property
    def mechanism_ids(self) -> tuple[str, ...]:
        return tuple(mechanism.mechanism_id for mechanism in self.mechanisms)