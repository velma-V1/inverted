from __future__ import annotations

from dataclasses import dataclass

from .cases import HarvestCase
from .models import ModelAdapter
from .runner import ModelTrialRunner, TrialResult
from .telemetry import SystemInvolvement
from .types import RouteMode

class BudgetExceeded(RuntimeError):
    pass

class CallBudget:
    def __init__(self, ceiling: int) -> None:
        if ceiling < 0: raise ValueError("ceiling must be nonnegative")
        self.ceiling = ceiling
        self.used = 0

    @property
    def remaining(self) -> int:
        return self.ceiling - self.used

    def consume(self, count: int = 1) -> None:
        if count < 1: raise ValueError("count must be positive")
        if self.used + count > self.ceiling: raise BudgetExceeded(f"call budget exceeded: {self.used + count}>{self.ceiling}")
        self.used += count

@dataclass(frozen=True)
class ExperimentArm:
    name: str
    adapter: ModelAdapter
    route: RouteMode
    involvement: SystemInvolvement
    system_prompt: str | None = None

class MatchedExperimentRunner:
    def __init__(self, budget: CallBudget, trial_runner: ModelTrialRunner | None = None) -> None:
        self.budget = budget
        self.trial_runner = trial_runner or ModelTrialRunner()

    def run(self, cases: list[HarvestCase], arms: list[ExperimentArm]) -> list[TrialResult]:
        results: list[TrialResult] = []
        for case in cases:
            for arm in arms:
                self.budget.consume()
                results.append(self.trial_runner.run(case, arm.adapter, route=arm.route, involvement=arm.involvement, system_prompt=arm.system_prompt))
        return results

class BoundaryPlanner:
    def __init__(self, cases: list[HarvestCase]) -> None:
        if not cases: raise ValueError("boundary planner needs cases")
        self.cases = sorted(cases, key=lambda c: (c.difficulty, c.case_id))

    def next_case(self, observations: list[tuple[HarvestCase, bool]]) -> HarvestCase | None:
        tested_ids = {c.case_id for c, _ in observations}
        untested = [c for c in self.cases if c.case_id not in tested_ids]
        if not untested: return None
        if not observations: return untested[len(untested) // 2]
        successes = [c.difficulty for c, ok in observations if ok]
        failures = [c.difficulty for c, ok in observations if not ok]
        if successes and failures:
            midpoint = (max(successes) + min(failures)) / 2
            return min(untested, key=lambda c: (abs(c.difficulty - midpoint), c.difficulty, c.case_id))
        if successes:
            target = max(successes) + 1
            return min(untested, key=lambda c: (abs(c.difficulty - target), c.difficulty, c.case_id))
        target = min(failures) - 1
        return min(untested, key=lambda c: (abs(c.difficulty - target), -c.difficulty, c.case_id))
