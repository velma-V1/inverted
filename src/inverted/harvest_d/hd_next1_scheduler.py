from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import random
from typing import Iterable

from .types import SequentialDecision


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    mechanism_id: str
    model_key: str
    decision_id: str
    decision_change_reason: str
    hard_invariant_uncertainty: float = 0.0
    architecture_changing_uncertainty: float = 0.0
    can_change_winner: float = 0.0
    uncovered_high_value_interaction: float = 0.0
    model_family_conditional_uncertainty: float = 0.0
    minimum_support_uncertainty: float = 0.0
    negative_transfer_boundary: float = 0.0
    expected_seconds: float = 1.0
    protected_random: bool = False


def qwen_call_is_decision_relevant(candidate: Candidate) -> bool:
    if candidate.model_key != "QWEN":
        return True
    return bool(candidate.decision_id and candidate.decision_change_reason.strip())


@dataclass
class HDNext1Scheduler:
    seed: int
    protected_random_fraction: float = 0.10
    decisions: dict[str, SequentialDecision] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.10 <= float(self.protected_random_fraction) <= 1.0:
            raise ValueError("HD-NEXT-1 protected random stream must be at least 10%")

    def observe(self, mechanism_id: str, decision: SequentialDecision) -> None:
        self.decisions[str(mechanism_id)] = SequentialDecision(decision)

    def allowed_kinds(self, mechanism_id: str) -> tuple[str, ...]:
        decision = self.decisions.get(str(mechanism_id), SequentialDecision.UNRESOLVED)
        if decision is SequentialDecision.HARMFUL:
            return ("CONTRADICTION_CHECK",)
        if decision is SequentialDecision.FUTILE:
            return ()
        if decision is SequentialDecision.NONINFERIOR:
            return ("MINIMALITY", "CONTRADICTION_CHECK")
        return ("EXPERIMENT", "CONTRADICTION_CHECK")

    @staticmethod
    def _priority(row: Candidate) -> tuple[float, ...]:
        return (
            row.hard_invariant_uncertainty,
            row.architecture_changing_uncertainty,
            row.can_change_winner,
            row.uncovered_high_value_interaction,
            row.model_family_conditional_uncertainty,
            row.minimum_support_uncertainty,
            row.negative_transfer_boundary,
            -row.expected_seconds,
        )

    def plan_block(self, candidates: Iterable[Candidate], *, block_size: int) -> tuple[Candidate, ...]:
        if block_size < 1:
            return ()
        rows = [row for row in candidates if self.allowed_kinds(row.mechanism_id) and qwen_call_is_decision_relevant(row)]
        if not rows:
            return ()
        random_count = min(len(rows), max(1, math.ceil(block_size * self.protected_random_fraction)))
        rng = random.Random(int(self.seed))
        shuffled = list(rows)
        rng.shuffle(shuffled)
        protected_ids = {row.candidate_id for row in shuffled[:random_count]}
        protected = [replace(row, protected_random=True) for row in rows if row.candidate_id in protected_ids]
        ranked = [row for row in rows if row.candidate_id not in protected_ids]
        ranked.sort(key=lambda row: (self._priority(row), row.candidate_id), reverse=True)
        result = protected + ranked
        return tuple(result[: min(block_size, len(result))])
