from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CounterfactualStatus(str, Enum):
    CAUSAL_REPLAY = "CAUSAL_REPLAY"
    REQUIRES_NEW_INFERENCE = "REQUIRES_NEW_INFERENCE"
    INVALID_COUNTERFACTUAL = "INVALID_COUNTERFACTUAL"


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    source_class: str
    path: str
    required: bool
    bundle_sha256: str | None = None
    git_sha: str | None = None
    run_id: str | None = None
    evidence_tier: str | None = None
    complete_claim: bool | None = None
    schema_version: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureProvenance:
    feature_name: str
    observed_at_transition: int | None = None
    derived_at_transition: int | None = None
    observed_at_timestamp: str | None = None
    derived_at_timestamp: str | None = None
    source_event_ids: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    available_before_action: bool | None = None
    contains_post_action_dependency: bool | None = None
    source_field: str | None = None
    derivation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceState:
    task_id: str
    task_family: str | None = None
    causal_twin_id: str | None = None
    holdout_id: str | None = None
    split: str | None = None
    complexity: int | float | None = None
    representation: str | None = None
    requirements: tuple[str, ...] = ()
    candidate_status: str | None = None
    prior_model: str | None = None
    prior_role: str | None = None
    prior_attempts: int = 0
    failure_signature: str | None = None
    failure_class: str | None = None
    deterministic_result: str | None = None
    semantic_result: str | None = None
    semantic_deterministic_disagreement: bool | None = None
    verifier_results: tuple[dict[str, Any], ...] = ()
    retrieved_experience: tuple[str, ...] = ()
    physical_calls_spent: int = 0
    logical_calls_spent: int | None = None
    tokens_spent: int | None = None
    prompt_tokens_spent: int | None = None
    completion_tokens_spent: int | None = None
    elapsed_ms: float | None = None
    cache_hits: int | None = None
    cache_misses: int | None = None
    feature_provenance: tuple[FeatureProvenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionRecord:
    component: str
    model: str | None = None
    role: str | None = None
    verifier: str | None = None
    operation: str | None = None
    retry_kind: str | None = None
    repair_kind: str | None = None
    changes_model_input: bool = False
    produces_new_model_output: bool = False
    prompt_fingerprint: str | None = None
    context_fingerprint: str | None = None
    selected_by: str | None = None
    selection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutcomeRecord:
    deterministic_result: str | None = None
    semantic_result: str | None = None
    hidden_gold_result: str | None = None
    success: bool | None = None
    catastrophic: bool | None = None
    blocked: bool | None = None
    failure_signature: str | None = None
    failure_class: str | None = None
    physical_calls_delta: int = 0
    logical_calls_delta: int | None = None
    tokens_delta: int | None = None
    prompt_tokens_delta: int | None = None
    completion_tokens_delta: int | None = None
    elapsed_ms_delta: float | None = None
    cache_hit: bool | None = None
    validator_count: int | None = None
    validator_disagreements: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionRecord:
    transition_id: str
    source_id: str
    state_before: EvidenceState
    action: ActionRecord
    state_after: OutcomeRecord
    observed: bool = True
    transition_index: int | None = None
    event_timestamp: str | None = None
    source_record_type: str | None = None
    raw_record_hash: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    anomalies: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CounterfactualRecord:
    counterfactual_id: str
    source_transition_ids: tuple[str, ...]
    proposed_actions: tuple[ActionRecord, ...]
    status: CounterfactualStatus
    reason: str
    analysis_only_oracle: bool = False
    dependency_audit: tuple[dict[str, Any], ...] = ()
    invalidity_flags: tuple[str, ...] = ()
    unresolved_fields: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ZeroModelCallGuard:
    physical_calls: int = 0
    attempted_calls: int = 0
    attempted_labels: list[str] = field(default_factory=list)

    def consume(self, label: str | None = None) -> None:
        self.attempted_calls += 1
        if label:
            self.attempted_labels.append(label)
        detail = f" ({label})" if label else ""
        raise RuntimeError(f"Section 0 permits zero physical model calls{detail}")
