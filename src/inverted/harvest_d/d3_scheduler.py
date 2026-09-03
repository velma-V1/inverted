from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Iterable

from .types import SequentialDecision


@dataclass(frozen=True)
class ExperimentCandidate:
    candidate_id: str
    mechanism_id: str
    kind: str = "EXPERIMENT"
    hard_invariant_uncertainty: float = 0.0
    semantic_uncertainty: float = 0.0
    silent_wrong_action_uncertainty: float = 0.0
    recovery_uncertainty: float = 0.0
    interaction_uncertainty: float = 0.0
    model_substitution_uncertainty: float = 0.0
    information_marginal_uncertainty: float = 0.0
    assistance_marginal_uncertainty: float = 0.0
    minimum_support_uncertainty: float = 0.0
    efficiency: float = 0.0
    sealed: bool = False

    def score_tuple(self) -> tuple[float, ...]:
        return (
            self.hard_invariant_uncertainty,
            self.semantic_uncertainty,
            self.silent_wrong_action_uncertainty,
            self.recovery_uncertainty,
            self.interaction_uncertainty,
            self.model_substitution_uncertainty,
            self.information_marginal_uncertainty,
            self.assistance_marginal_uncertainty,
            self.minimum_support_uncertainty,
            self.efficiency,
        )


@dataclass(frozen=True)
class ScheduledExperiment:
    candidate_id: str
    mechanism_id: str
    kind: str
    selection_mode: str
    priority_reason: str
    selection_probability: float
    alternatives: tuple[dict[str, object], ...] = ()


_PRIORITY_FIELDS: tuple[tuple[str, str], ...] = (
    ("hard_invariant_uncertainty", "HARD_INVARIANT_UNCERTAINTY"),
    ("semantic_uncertainty", "SEMANTIC_UNCERTAINTY"),
    ("silent_wrong_action_uncertainty", "SILENT_WRONG_ACTION_UNCERTAINTY"),
    ("recovery_uncertainty", "RECOVERY_UNCERTAINTY"),
    ("interaction_uncertainty", "INFORMATION_ASSISTANCE_INTERACTION"),
    ("model_substitution_uncertainty", "MODEL_SUBSTITUTION_UNCERTAINTY"),
    ("information_marginal_uncertainty", "INFORMATION_MARGINAL_UNCERTAINTY"),
    ("assistance_marginal_uncertainty", "ASSISTANCE_MARGINAL_UNCERTAINTY"),
    ("minimum_support_uncertainty", "MINIMUM_SUPPORT_UNCERTAINTY"),
    ("efficiency", "EFFICIENCY"),
)


@dataclass
class D3Scheduler:
    random_stream_fraction: float = 0.10
    seed: int = 20260903
    sealed_open: bool = False
    _selection_count: int = 0
    _decisions: dict[str, SequentialDecision] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.random_stream_fraction <= 1.0:
            raise ValueError("random_stream_fraction must be in [0,1]")
        self._rng = random.Random(self.seed)

    @classmethod
    def default(
        cls,
        *,
        random_stream_fraction: float = 0.10,
        seed: int = 20260903,
    ) -> "D3Scheduler":
        return cls(random_stream_fraction=random_stream_fraction, seed=seed)

    def observe(self, mechanism_id: str, decision: SequentialDecision) -> None:
        self._decisions[str(mechanism_id)] = decision

    def remaining_for(self, mechanism_id: str) -> tuple[ExperimentCandidate, ...]:
        if self._decisions.get(str(mechanism_id)) is SequentialDecision.HARMFUL:
            return (
                ExperimentCandidate(
                    candidate_id=f"{mechanism_id}:contradiction-check",
                    mechanism_id=str(mechanism_id),
                    kind="CONTRADICTION_CHECK",
                    hard_invariant_uncertainty=1.0,
                ),
            )
        return ()

    def _eligible(self, candidates: Iterable[ExperimentCandidate]) -> list[ExperimentCandidate]:
        eligible: list[ExperimentCandidate] = []
        for candidate in candidates:
            if candidate.sealed and not self.sealed_open:
                continue
            decision = self._decisions.get(candidate.mechanism_id)
            if decision is SequentialDecision.HARMFUL and candidate.kind != "CONTRADICTION_CHECK":
                continue
            eligible.append(candidate)
        if not eligible:
            raise RuntimeError("no admissible D3 experiment candidates")
        return eligible

    @staticmethod
    def _priority_reason(candidate: ExperimentCandidate) -> str:
        for field_name, reason in _PRIORITY_FIELDS:
            if float(getattr(candidate, field_name)) > 0.0:
                return reason
        return "EFFICIENCY"

    @staticmethod
    def _alternative_rows(candidates: list[ExperimentCandidate]) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "candidate_id": c.candidate_id,
                "mechanism_id": c.mechanism_id,
                "kind": c.kind,
                "score": list(c.score_tuple()),
                "sealed": c.sealed,
            }
            for c in candidates
        )

    def _is_protected_random_turn(self) -> bool:
        if self.random_stream_fraction <= 0.0:
            return False
        if self.random_stream_fraction >= 1.0:
            return True
        interval = max(1, int(round(1.0 / self.random_stream_fraction)))
        return self._selection_count % interval == 0

    def select_next(self, candidates: Iterable[ExperimentCandidate]) -> ScheduledExperiment:
        eligible = self._eligible(candidates)
        self._selection_count += 1
        alternatives = self._alternative_rows(eligible)

        if self._is_protected_random_turn():
            chosen = self._rng.choice(eligible)
            return ScheduledExperiment(
                candidate_id=chosen.candidate_id,
                mechanism_id=chosen.mechanism_id,
                kind=chosen.kind,
                selection_mode="PROTECTED_RANDOM",
                priority_reason="PROTECTED_RANDOM_EXPLORATION",
                selection_probability=1.0 / len(eligible),
                alternatives=alternatives,
            )

        # Python tuple ordering gives the frozen lexicographic objective. Stable
        # candidate_id tie-break keeps adaptive choices reproducible.
        chosen = max(eligible, key=lambda c: (c.score_tuple(), tuple(-ord(ch) for ch in c.candidate_id)))
        return ScheduledExperiment(
            candidate_id=chosen.candidate_id,
            mechanism_id=chosen.mechanism_id,
            kind=chosen.kind,
            selection_mode="ADAPTIVE",
            priority_reason=self._priority_reason(chosen),
            selection_probability=1.0,
            alternatives=alternatives,
        )
