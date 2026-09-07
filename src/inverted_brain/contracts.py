from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


@dataclass(frozen=True)
class DifficultyVector:
    constraints: int = 1
    dependency_depth: int = 1
    mutation_depth: int = 1
    stale_evidence_risk: int = 0
    distractors: int = 0
    repair_branching: int = 1
    negative_constraints: int = 0
    evidence_ambiguity: int = 0
    tool_pressure: int = 0
    temporal_depth: int = 0
    downstream_interaction: int = 0
    ontology_novelty: int = 0

    def key(self) -> tuple[int, ...]:
        return tuple(self.__dict__.values())


@dataclass
class TaskSpec:
    task_id: str
    grammar: str
    seed: int
    difficulty: DifficultyVector
    root: str


@dataclass
class AgentEvent:
    index: int
    kind: str
    actor: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str | None = None
    source_id: str | None = None


TrialStatus = Literal[
    "COMPLETE", "FAILED", "ABORTED_INFRASTRUCTURE",
    "INVALID_EVIDENCE", "TIMEOUT",
]


@dataclass
class TrialResult:
    trial_id: str
    arm: str
    status: TrialStatus | str
    outcome_passed: bool
    process_passed: bool
    events: list[AgentEvent] = field(default_factory=list)
    workspace: str | None = None
    wall_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstraintEvaluation:
    constraint_id: str
    event_index: int
    status: Literal["satisfied", "violated", "unknown"]
    recoverable: bool = True
    evidence: list[str] = field(default_factory=list)


@dataclass
class CriticalDivergence:
    task_id: str
    qwen_index: int
    teacher_index: int | None
    failure_class: str
    evidence: list[str] = field(default_factory=list)
    candidate_behavior: str | None = None
    confidence: float = 0.0


@dataclass
class InterventionSpec:
    intervention_id: str
    kind: Literal["remove", "replace", "delay", "force", "interaction"]
    target_kind: str
    replacement: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayResult:
    intervention_id: str
    repetitions: int
    passes: int
    failures: int
    effect: float
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class MechanismCandidate:
    candidate_id: str
    trigger: str
    baseline_behavior: str
    replacement_behavior: str
    evidence_ids: list[str]
    scope: list[str]
    cost: dict[str, float] = field(default_factory=dict)
    counterevidence: list[str] = field(default_factory=list)
    status: str = "proposed"


@dataclass
class RetentionDecision:
    retained: bool
    reasons: list[str]
    fresh_lift: int
    regressions: int
    bounded_scope: str | None = None


class LearningDestination(str, Enum):
    BRAIN = "BRAIN"
    SYSTEM = "SYSTEM"
    SKILL = "SKILL"
    TOOL_HAND = "TOOL_HAND"
    MEMORY = "MEMORY"
    NEGATIVE_EVIDENCE = "NEGATIVE_EVIDENCE"


@dataclass(frozen=True)
class LearnedArtifact:
    artifact_id: str
    source_candidate_id: str
    destination: LearningDestination
    artifact_kind: str
    trigger: str
    content: str
    evidence_ids: list[str]
    scope: list[str]
    boundary_conditions: list[str]
    failure_modes: list[str]
    counterevidence: list[str]
    verification: list[str]
    provenance: list[str]
    source_status: str
    cost: dict[str, float] = field(default_factory=dict)
