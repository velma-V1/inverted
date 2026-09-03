from __future__ import annotations

from dataclasses import dataclass, replace

from .frontier import CapabilityEnvelope, CapabilityKey
from .types import CapabilityState, PromotionState


class PromotionError(ValueError):
    pass


@dataclass(frozen=True)
class PromotionEvidence:
    same_state: bool = False
    targeted_success: bool = False
    sham_success: bool = False
    neighbor_passed: bool = False
    fresh_passed: bool = False
    regression_safe: bool = False
    hard_invariant_violation: bool = False
    authority_expansion: bool = False


@dataclass(frozen=True)
class KnowledgeObject:
    knowledge_id: str
    version: int
    originating_failure_signature: str
    causal_hypothesis: str
    verified_mechanism: str
    source_model: str = ""
    state: PromotionState = PromotionState.OBSERVED
    rollback_target: int | None = None


@dataclass(frozen=True)
class RatchetMetrics:
    capability_expansion_rate: float | None
    qwen_retirement_rate: float | None
    small_model_takeover_rate: float | None
    knowledge_reuse_rate: float | None
    negative_transfer_rate: float | None
    capability_regression_rate: float | None


_ALLOWED_AUTOMATIC_KEYS = {
    "routing_preference", "scaffold_preference", "evidence_strategy", "context_strategy",
    "decomposition_template", "recovery_recommendation", "failure_signature",
    "verified_skill", "deterministic_guard",
}


class KnowledgeRegistry:
    def __init__(self) -> None:
        self._objects: dict[str, KnowledgeObject] = {}
        self._history: dict[str, list[KnowledgeObject]] = {}
        self._envelope_history: list[CapabilityEnvelope] = []

    def add(self, obj: KnowledgeObject) -> None:
        if obj.knowledge_id in self._objects:
            raise PromotionError("duplicate knowledge_id")
        if obj.state is not PromotionState.OBSERVED:
            raise PromotionError("new knowledge must start OBSERVED")
        self._objects[obj.knowledge_id] = obj
        self._history[obj.knowledge_id] = [obj]

    def get(self, knowledge_id: str) -> KnowledgeObject:
        return self._objects[knowledge_id]

    def _store(self, obj: KnowledgeObject) -> KnowledgeObject:
        self._objects[obj.knowledge_id] = obj
        self._history[obj.knowledge_id].append(obj)
        return obj

    def advance(self, knowledge_id: str, target: PromotionState, evidence: PromotionEvidence, *, actor: str) -> KnowledgeObject:
        current = self.get(knowledge_id)
        if current.state is PromotionState.SUSPENDED:
            raise PromotionError("suspended knowledge cannot advance")
        if evidence.hard_invariant_violation:
            return self._store(replace(current, version=current.version + 1, state=PromotionState.SUSPENDED, rollback_target=current.version))
        if evidence.authority_expansion:
            raise PromotionError("knowledge promotion cannot expand execution authority")
        if actor == "model" and target not in {PromotionState.OBSERVED, PromotionState.HYPOTHESIZED}:
            raise PromotionError("model actor cannot self-promote")
        expected_next = {
            PromotionState.OBSERVED: PromotionState.HYPOTHESIZED,
            PromotionState.HYPOTHESIZED: PromotionState.CAUSALLY_VERIFIED,
            PromotionState.CAUSALLY_VERIFIED: PromotionState.NEIGHBOR_GENERALIZED,
            PromotionState.NEIGHBOR_GENERALIZED: PromotionState.FRESH_GENERALIZED,
            PromotionState.FRESH_GENERALIZED: PromotionState.REGRESSION_SAFE,
            PromotionState.REGRESSION_SAFE: PromotionState.PROMOTED,
        }.get(current.state)
        if target is not expected_next:
            raise PromotionError(f"illegal promotion transition {current.state} -> {target}")
        if target is PromotionState.CAUSALLY_VERIFIED and not (evidence.same_state and evidence.targeted_success and not evidence.sham_success):
            raise PromotionError("causal verification requires same-state target success over sham")
        if target is PromotionState.NEIGHBOR_GENERALIZED and not evidence.neighbor_passed:
            raise PromotionError("neighbor generalization gate failed")
        if target is PromotionState.FRESH_GENERALIZED and not evidence.fresh_passed:
            raise PromotionError("fresh generalization gate failed")
        if target is PromotionState.REGRESSION_SAFE and not evidence.regression_safe:
            raise PromotionError("regression-safe gate failed")
        return self._store(replace(current, version=current.version + 1, state=target, rollback_target=current.version))

    def suspend_on_evidence(self, knowledge_id: str, evidence: PromotionEvidence) -> KnowledgeObject:
        current = self.get(knowledge_id)
        if not evidence.hard_invariant_violation:
            return current
        return self._store(replace(current, version=current.version + 1, state=PromotionState.SUSPENDED, rollback_target=current.version))

    def validate_automatic_change(self, change: dict[str, object]) -> None:
        if change.get("authority_expansion"):
            raise PromotionError("automatic knowledge cannot expand authority")
        illegal = set(change) - _ALLOWED_AUTOMATIC_KEYS - {"authority_expansion"}
        if illegal:
            raise PromotionError(f"unsupported automatic knowledge mutation: {sorted(illegal)}")

    def apply_envelope_update(self, envelope: CapabilityEnvelope, key: CapabilityKey, state: CapabilityState) -> CapabilityEnvelope:
        self._envelope_history.append(envelope)
        return envelope.with_state(key, state)

    def rollback_envelope(self) -> CapabilityEnvelope:
        if not self._envelope_history:
            raise PromotionError("no envelope rollback target")
        return self._envelope_history.pop()


def _rate(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def ratchet_metrics(*, investigated: int, externalized: int, previously_qwen_required: int, qwen_retired: int,
                    transfer_eligible: int, small_takeovers: int, applicable_future: int, reused: int,
                    prior_correct_exposed: int, harmed: int, territory_before: int, territory_after: int) -> RatchetMetrics:
    lost = max(0, territory_before - territory_after)
    return RatchetMetrics(_rate(externalized, investigated), _rate(qwen_retired, previously_qwen_required),
                          _rate(small_takeovers, transfer_eligible), _rate(reused, applicable_future),
                          _rate(harmed, prior_correct_exposed), _rate(lost, territory_before))
