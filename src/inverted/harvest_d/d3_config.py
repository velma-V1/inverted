from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class D3BudgetError(ValueError):
    pass


class D3Phase(str, Enum):
    BASELINE = "D3.1"
    INFORMATION = "D3.2"
    REPRESENTATION = "D3.3"
    ASSISTANCE = "D3.4"
    RECOVERY = "D3.5"
    COMBINED = "D3.6"
    NEGATIVE_TRANSFER = "D3.7"
    SEALED_CONFIRMATION = "D3.8"


D3_PHASE_RESERVOIRS: dict[D3Phase, int] = {
    D3Phase.BASELINE: 80,
    D3Phase.INFORMATION: 150,
    D3Phase.REPRESENTATION: 120,
    D3Phase.ASSISTANCE: 150,
    D3Phase.RECOVERY: 150,
    D3Phase.COMBINED: 160,
    D3Phase.NEGATIVE_TRANSFER: 90,
    D3Phase.SEALED_CONFIRMATION: 100,
}


@dataclass
class D3BudgetState:
    current_ceilings: dict[D3Phase, int] = field(default_factory=lambda: dict(D3_PHASE_RESERVOIRS))
    used_by_phase: dict[D3Phase, int] = field(
        default_factory=lambda: {phase: 0 for phase in D3_PHASE_RESERVOIRS}
    )

    @classmethod
    def default(cls) -> "D3BudgetState":
        return cls()

    @property
    def total_ceiling(self) -> int:
        return sum(self.current_ceilings.values())

    @property
    def used(self) -> int:
        return sum(self.used_by_phase.values())

    @property
    def remaining(self) -> int:
        return self.total_ceiling - self.used

    @property
    def sealed_remaining(self) -> int:
        return self.phase_remaining(D3Phase.SEALED_CONFIRMATION)

    @property
    def remaining_unsealed(self) -> int:
        return sum(
            self.phase_remaining(phase)
            for phase in D3Phase
            if phase is not D3Phase.SEALED_CONFIRMATION
        )

    def phase_ceiling(self, phase: D3Phase) -> int:
        return self.current_ceilings[phase]

    def phase_remaining(self, phase: D3Phase) -> int:
        return self.current_ceilings[phase] - self.used_by_phase[phase]

    def reserve_call(self, phase: D3Phase) -> None:
        if self.phase_remaining(phase) <= 0:
            raise D3BudgetError(f"D3 phase {phase.value} call reservoir exhausted")
        if self.remaining <= 0:
            raise D3BudgetError("D3 1000-call ceiling exhausted")
        self.used_by_phase[phase] += 1

    def reallocate_calls(
        self,
        source: D3Phase,
        target: D3Phase,
        count: int,
        *,
        reason: str,
    ) -> None:
        if not reason.strip():
            raise D3BudgetError("D3 reallocation requires a recorded reason")
        if count <= 0:
            raise D3BudgetError("D3 reallocation count must be positive")
        if source is target:
            raise D3BudgetError("D3 reallocation source and target must differ")
        if source is D3Phase.SEALED_CONFIRMATION:
            raise D3BudgetError("D3 sealed-confirmation reserve is protected")
        if count > self.phase_remaining(source):
            raise D3BudgetError("cannot reallocate calls already spent or outside source reservoir")

        before = self.total_ceiling
        self.current_ceilings[source] -= count
        self.current_ceilings[target] += count
        if self.total_ceiling != before:
            raise D3BudgetError("D3 reallocation changed the absolute call ceiling")
