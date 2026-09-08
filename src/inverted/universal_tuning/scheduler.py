from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping

from .core import Profile, profile_fingerprint
from .statistics import (
    PairedBatch,
    classify_comparison,
    paired_bootstrap_ci,
)
from .tasks import TASK_FAMILIES, TaskPool

BATCH_SIZE = 5
STAGES = ("gate", "budget", "temperature", "interaction", "holdout", "screen")


@dataclass(frozen=True)
class ModelMetadata:
    general_thinking_temperature: float = 1.0
    coding_thinking_temperature: float = 0.6
    direct_temperature: float = 0.7
    gate_thinking_budget: int = 1024
    diagnostic_budget: int = 2048


@dataclass(frozen=True)
class ScheduledTrial:
    trial_id: str
    batch_id: str
    family: str
    stage: str
    profile: Profile
    task_ids: tuple[str, ...]
    inference_seed: int
    decision_reason: str

    @property
    def physical_calls(self) -> int:
        return 2 if self.profile.thinking else 1


@dataclass(frozen=True)
class ModeDecision:
    mode: str
    status: str
    next_stage: str


@dataclass(frozen=True)
class BudgetDecision:
    selected_budget: int
    reference_budget: int
    inferior_budgets: tuple[int, ...]
    unresolved_budgets: tuple[int, ...] = ()
    status: str = "RESOLVED"


@dataclass(frozen=True)
class TemperatureSurface:
    kind: str
    lower: float
    upper: float
    recommended: float | None
    optimum: float | None
    resolution: float
    needs_refinement: bool


def _paired_batches(baseline: Iterable[float], candidate: Iterable[float]) -> tuple[PairedBatch, ...]:
    left = tuple(float(x) for x in baseline)
    right = tuple(float(x) for x in candidate)
    if not left or len(left) != len(right) or len(left) % BATCH_SIZE:
        raise ValueError("paired outcomes must be equal, non-empty, and divisible by batch size")
    return tuple(
        PairedBatch(f"batch-{i // BATCH_SIZE:03d}", left[i:i+BATCH_SIZE], right[i:i+BATCH_SIZE])
        for i in range(0, len(left), BATCH_SIZE)
    )


def _rate(values: Iterable[float]) -> float:
    rows = tuple(float(x) for x in values)
    if not rows:
        raise ValueError("outcomes required")
    return sum(rows) / len(rows)


def select_mode(
    direct: Iterable[float], thinking: Iterable[float], *,
    direct_contract_rate: float = 1.0, thinking_contract_rate: float = 1.0,
    direct_completion_rate: float = 1.0, thinking_completion_rate: float = 1.0,
    reliability_gain_floor: float = 0.05,
    bootstrap_seed: int = 20260907, acceptable_semantic_floor: float = 0.90,
    minimum_useful_effect: float = 0.05, noninferiority_margin: float = -0.02,
    final_checkpoint: int = 120,
) -> ModeDecision:
    direct_rows = tuple(direct)
    thinking_rows = tuple(thinking)
    direct_rate = _rate(direct_rows)
    thinking_rate = _rate(thinking_rows)
    if max(direct_rate, thinking_rate) < acceptable_semantic_floor:
        if len(direct_rows) >= final_checkpoint:
            return ModeDecision("unresolved", "CAPABILITY_UNRESOLVED", "capability_diagnostic")
        return ModeDecision("unresolved", "EVIDENCE_CLOSE", "gate")
    comparison = paired_bootstrap_ci(
        _paired_batches(direct_rows, thinking_rows), seed=bootstrap_seed
    )
    status = classify_comparison(
        comparison, superiority_margin=minimum_useful_effect,
        noninferiority_margin=noninferiority_margin,
    )
    if status == "SUPERIOR":
        return ModeDecision("thinking", "THINKING_SUPERIOR", "budget")
    if status in {"INSUFFICIENT", "CLOSE"}:
        return ModeDecision("unresolved", "EVIDENCE_CLOSE", "gate")
    contract_gain = thinking_contract_rate - direct_contract_rate
    completion_gain = thinking_completion_rate - direct_completion_rate
    if contract_gain >= reliability_gain_floor or completion_gain >= reliability_gain_floor:
        return ModeDecision("thinking", "THINKING_RELIABILITY_SUPERIOR", "budget")
    if direct_contract_rate < 0.8 and thinking_contract_rate < 0.8:
        return ModeDecision("direct", "CONTRACT_LIMITED", "holdout")
    return ModeDecision("direct", "DIRECT_SUFFICIENT", "holdout")


def select_minimum_budget(
    outcomes: Mapping[int, Iterable[float]], *, bootstrap_seed: int = 20260907,
    noninferiority_margin: float = -0.02,
) -> BudgetDecision:
    if not outcomes:
        raise ValueError("budget outcomes required")
    frozen = {int(k): tuple(v) for k, v in outcomes.items()}
    best_rate = max(_rate(v) for v in frozen.values())
    reference = min(k for k, v in frozen.items() if _rate(v) == best_rate)
    inferior: list[int] = []
    unresolved: list[int] = []
    noninferior: list[int] = []
    n_atomic = len(next(iter(frozen.values())))
    for budget in sorted(frozen):
        comparison = paired_bootstrap_ci(
            _paired_batches(frozen[reference], frozen[budget]),
            seed=bootstrap_seed + budget,
        )
        if comparison.ci_low >= noninferiority_margin:
            noninferior.append(budget)
        elif comparison.ci_high < noninferiority_margin:
            inferior.append(budget)
        else:
            unresolved.append(budget)
    status = "EVIDENCE_CLOSE" if unresolved and n_atomic < 120 else "RESOLVED"
    return BudgetDecision(
        min(noninferior), reference, tuple(inferior), tuple(unresolved), status
    )


def discover_temperature_surface(
    outcomes: Mapping[float, Iterable[float]], *, bootstrap_seed: int = 20260907,
    minimum_useful_effect: float = 0.05, noninferiority_margin: float = -0.02,
) -> TemperatureSurface:
    if len(outcomes) < 2:
        raise ValueError("at least two temperatures are required")
    frozen = {round(float(k), 6): tuple(v) for k, v in outcomes.items()}
    temps = sorted(frozen)
    rates = {temp: _rate(frozen[temp]) for temp in temps}
    best_rate = max(rates.values())
    best_temps = [temp for temp in temps if rates[temp] == best_rate]
    reference = min(best_temps, key=lambda x: abs(x - sum(temps) / len(temps)))
    noninferior: list[float] = []
    inferior: list[float] = []
    unresolved: list[float] = []
    for index, temp in enumerate(temps):
        comparison = paired_bootstrap_ci(
            _paired_batches(frozen[reference], frozen[temp]),
            seed=bootstrap_seed + index,
        )
        if comparison.ci_low >= noninferiority_margin:
            noninferior.append(temp)
        elif comparison.ci_high < noninferiority_margin:
            inferior.append(temp)
        else:
            unresolved.append(temp)
    spacing = min((b - a for a, b in zip(temps, temps[1:])), default=1.0)
    n_atomic = len(next(iter(frozen.values())))
    if unresolved and n_atomic < 120:
        return TemperatureSurface(
            "EVIDENCE_CLOSE", min(temps), max(temps), reference, None, spacing, False
        )
    survivors = sorted(set(noninferior + (unresolved if n_atomic >= 120 else [])))
    if len(survivors) > 1:
        middle = sum(survivors) / len(survivors)
        recommended = min(survivors, key=lambda x: (abs(x - middle), x))
        return TemperatureSurface(
            "PLATEAU", min(survivors), max(survivors), recommended, None, spacing, False
        )
    winner = survivors[0] if survivors else reference
    superior_to_all = True
    for index, temp in enumerate(temps):
        if temp == winner:
            continue
        superiority = paired_bootstrap_ci(
            _paired_batches(frozen[temp], frozen[winner]),
            seed=bootstrap_seed + 1000 + index,
        )
        if classify_comparison(
            superiority, superiority_margin=minimum_useful_effect,
            noninferiority_margin=noninferiority_margin,
        ) != "SUPERIOR":
            superior_to_all = False
            break
    if spacing <= 0.0011 and len(inferior) == len(temps) - 1:
        if superior_to_all:
            return TemperatureSurface(
                "OPTIMUM", winner, winner, winner, winner, spacing, False
            )
        if n_atomic < 120:
            return TemperatureSurface(
                "EVIDENCE_CLOSE", min(temps), max(temps), winner, None, spacing, False
            )
        return TemperatureSurface(
            "UNRESOLVED_POINT", min(temps), max(temps), winner, None, spacing, False
        )
    return TemperatureSurface(
        "UNRESOLVED_POINT", min(temps), max(temps), winner, None, spacing, True
    )


def _stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


class AdaptiveScheduler:
    def __init__(self, pool: TaskPool, metadata: ModelMetadata) -> None:
        self.pool = pool
        self.metadata = metadata
        self._by_family = {
            family: tuple(task for task in pool.tasks if task.family == family)
            for family in TASK_FAMILIES
        }

    def partition_task_ids(self, family: str, stage: str, count: int = 120) -> tuple[str, ...]:
        if family not in self._by_family or stage not in STAGES:
            raise ValueError("unknown family or stage")
        rows = self._by_family[family]
        stage_index = STAGES.index(stage)
        start = stage_index * count
        if start + count <= len(rows):
            selected = rows[start:start + count]
        elif stage == "gate" and count <= len(rows):
            selected = rows[:count]
        else:
            raise ValueError("task pool does not contain full stage geometry")
        return tuple(task.task_id for task in selected)

    def paired_trials(
        self, *, family: str, stage: str, baseline: Profile, candidate: Profile,
        atomic_count: int, task_offset: int, decision_reason: str,
    ) -> tuple[ScheduledTrial, ...]:
        if atomic_count < BATCH_SIZE or atomic_count % BATCH_SIZE:
            raise ValueError("atomic_count must be a positive multiple of five")
        partition = self.partition_task_ids(family, stage, 120)
        chosen = partition[task_offset:task_offset + atomic_count]
        if len(chosen) != atomic_count:
            raise ValueError("requested atomic tasks exceed stage partition")
        trials: list[ScheduledTrial] = []
        for offset in range(0, atomic_count, BATCH_SIZE):
            task_ids = tuple(chosen[offset:offset + BATCH_SIZE])
            batch_no = (task_offset + offset) // BATCH_SIZE
            batch_id = f"{family}:{stage}:{batch_no:03d}"
            seed = _stable_seed(self.pool.seed, family, stage, batch_no)
            ordered = [("baseline", baseline), ("candidate", candidate)]
            if batch_no % 2:
                ordered.reverse()
            for label, profile in ordered:
                trials.append(ScheduledTrial(
                    trial_id=f"{batch_id}:{label}:{profile_fingerprint(profile)[:16]}",
                    batch_id=batch_id, family=family, stage=stage, profile=profile,
                    task_ids=task_ids, inference_seed=seed, decision_reason=decision_reason,
                ))
        return tuple(trials)

    @staticmethod
    def projected_physical_calls(trials: Iterable[ScheduledTrial]) -> int:
        return sum(trial.physical_calls for trial in trials)


@dataclass(frozen=True)
class HoldoutDecision:
    status: str
    certified: bool
    next_atomic_count: int
    baseline_rate: float
    candidate_rate: float
    delta: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class InteractionDecision:
    profile: Profile
    status: str
    changed_by_interaction: bool


def evaluate_holdout(
    baseline: Iterable[float], candidate: Iterable[float], *,
    bootstrap_seed: int = 20260907,
) -> HoldoutDecision:
    from .statistics import required_checkpoint
    comparison = paired_bootstrap_ci(
        _paired_batches(baseline, candidate), seed=bootstrap_seed
    )
    status = classify_comparison(comparison)
    certified = status in {"SUPERIOR", "INFERIOR", "EQUIVALENT", "TIE_OR_PLATEAU"}
    return HoldoutDecision(
        status, certified, required_checkpoint(comparison),
        comparison.baseline_rate, comparison.candidate_rate, comparison.delta,
        comparison.ci_low, comparison.ci_high,
    )


def select_interaction_profile(
    outcomes: Mapping[Profile, Iterable[float]], *, bootstrap_seed: int = 20260907,
) -> InteractionDecision:
    if not outcomes:
        raise ValueError("interaction outcomes required")
    frozen = {profile: tuple(values) for profile, values in outcomes.items()}
    rates = {profile: _rate(values) for profile, values in frozen.items()}
    ordered = sorted(
        frozen, key=lambda p: (rates[p], -p.thinking_budget, -abs(p.temperature - 0.8)), reverse=True
    )
    best = ordered[0]
    tied = [profile for profile in ordered if rates[profile] == rates[best]]
    if len(tied) > 1:
        chosen = min(tied, key=lambda p: (p.thinking_budget, abs(p.temperature - 0.8)))
        return InteractionDecision(chosen, "INTERACTION_PLATEAU", False)
    if len(ordered) == 1:
        return InteractionDecision(best, "INTERACTION_UNTESTED", False)
    runner_up = ordered[1]
    comparison = paired_bootstrap_ci(
        _paired_batches(frozen[runner_up], frozen[best]), seed=bootstrap_seed
    )
    resolved = classify_comparison(comparison) == "SUPERIOR"
    return InteractionDecision(
        best,
        "INTERACTION_RESOLVED" if resolved else "INTERACTION_CLOSE",
        resolved,
    )
