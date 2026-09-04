from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ClosureDecision(str, Enum):
    SUPERIOR = "SUPERIOR"
    NONINFERIOR = "NONINFERIOR"
    HARMFUL = "HARMFUL"
    FUTILE = "FUTILE"
    UNRESOLVED = "UNRESOLVED"


_DEFAULT_CEILINGS = {
    "C1": 24,
    "C2": 36,
    "C3": 36,
    "C4": 24,
    "C5": 24,
    "C6": 8,
    "C7": 48,
}


@dataclass
class ClosureBudget:
    ceilings: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_CEILINGS))

    @classmethod
    def default(cls) -> "ClosureBudget":
        return cls()

    @property
    def total_ceiling(self) -> int:
        return sum(self.ceilings.values())

    def ceiling(self, block: str) -> int:
        return int(self.ceilings[block])

    def reallocate(self, source: str, target: str, count: int, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("reallocation requires a recorded reason")
        if source == "C7":
            raise ValueError("protected confirmation budget may not be borrowed")
        if source == target:
            raise ValueError("source and target must differ")
        if count <= 0:
            raise ValueError("count must be positive")
        if source not in self.ceilings or target not in self.ceilings:
            raise ValueError("unknown closure budget block")
        if self.ceilings[source] < count:
            raise ValueError("cannot reallocate more than source ceiling")
        before = self.total_ceiling
        self.ceilings[source] -= count
        self.ceilings[target] += count
        if self.total_ceiling != before:
            raise RuntimeError("reallocation changed absolute closure ceiling")


@dataclass
class ClosureScheduler:
    decisions: dict[str, ClosureDecision] = field(default_factory=dict)

    def observe(self, mechanism_id: str, decision: ClosureDecision) -> None:
        self.decisions[str(mechanism_id)] = ClosureDecision(decision)

    def next_mode(self, mechanism_id: str) -> str | None:
        decision = self.decisions.get(str(mechanism_id), ClosureDecision.UNRESOLVED)
        if decision is ClosureDecision.SUPERIOR:
            return "DEEPEN_OR_ABLATE"
        if decision is ClosureDecision.NONINFERIOR:
            return "MINIMUM_SUPPORT_SEARCH"
        if decision is ClosureDecision.HARMFUL:
            return "CONTRADICTION_CHECK"
        if decision is ClosureDecision.FUTILE:
            return None
        return "DISCRIMINATE"

    def allowed_kinds(self, mechanism_id: str) -> tuple[str, ...]:
        decision = self.decisions.get(str(mechanism_id))
        if decision is ClosureDecision.HARMFUL:
            return ("CONTRADICTION_CHECK",)
        if decision is ClosureDecision.FUTILE:
            return ()
        return ("EXPERIMENT", "CONTRADICTION_CHECK")
