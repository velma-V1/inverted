from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable

SUPERIORITY_MARGIN = 0.05
NONINFERIORITY_MARGIN = -0.02
MIN_CERTIFICATION_ATOMIC = 40
CHECKPOINTS = (40, 60, 80, 120)


@dataclass(frozen=True)
class PairedBatch:
    batch_id: str
    baseline: tuple[float, ...]
    candidate: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.baseline or len(self.baseline) != len(self.candidate):
            raise ValueError("paired batch requires equal non-empty outcomes")


@dataclass(frozen=True)
class PairedComparison:
    n_batches: int
    n_atomic: int
    baseline_rate: float
    candidate_rate: float
    delta: float
    ci_low: float
    ci_high: float
    bootstrap_seed: int
    bootstrap_iterations: int


def _rates(batches: Iterable[PairedBatch]) -> tuple[float, float, int]:
    rows = tuple(batches)
    total = sum(len(row.baseline) for row in rows)
    if total == 0:
        raise ValueError("paired comparison requires outcomes")
    baseline = sum(sum(row.baseline) for row in rows) / total
    candidate = sum(sum(row.candidate) for row in rows) / total
    return baseline, candidate, total


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires values")
    position = (len(sorted_values) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def paired_bootstrap_ci(
    batches: Iterable[PairedBatch], *, seed: int = 20260907,
    iterations: int = 4000, confidence: float = 0.95,
) -> PairedComparison:
    rows = tuple(batches)
    if not rows or iterations < 100:
        raise ValueError("paired bootstrap requires batches and at least 100 iterations")
    baseline, candidate, n_atomic = _rates(rows)
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(iterations):
        sample = tuple(rows[rng.randrange(len(rows))] for _ in range(len(rows)))
        base_rate, cand_rate, _ = _rates(sample)
        deltas.append(cand_rate - base_rate)
    deltas.sort()
    alpha = (1.0 - confidence) / 2.0
    return PairedComparison(
        n_batches=len(rows), n_atomic=n_atomic,
        baseline_rate=baseline, candidate_rate=candidate,
        delta=candidate - baseline,
        ci_low=_quantile(deltas, alpha), ci_high=_quantile(deltas, 1.0 - alpha),
        bootstrap_seed=seed, bootstrap_iterations=iterations,
    )


def classify_comparison(
    comparison: PairedComparison, *, superiority_margin: float = SUPERIORITY_MARGIN,
    noninferiority_margin: float = NONINFERIORITY_MARGIN,
) -> str:
    if comparison.n_atomic < MIN_CERTIFICATION_ATOMIC:
        return "INSUFFICIENT"
    if comparison.ci_low >= superiority_margin:
        return "SUPERIOR"
    if comparison.ci_high < noninferiority_margin:
        return "INFERIOR"
    if comparison.ci_low >= noninferiority_margin and comparison.ci_high < superiority_margin:
        return "EQUIVALENT"
    if comparison.n_atomic >= CHECKPOINTS[-1]:
        return "TIE_OR_PLATEAU"
    return "CLOSE"


def required_checkpoint(comparison: PairedComparison) -> int:
    status = classify_comparison(comparison)
    if status == "INSUFFICIENT":
        return MIN_CERTIFICATION_ATOMIC
    if status != "CLOSE":
        return min(max(comparison.n_atomic, MIN_CERTIFICATION_ATOMIC), CHECKPOINTS[-1])
    for checkpoint in CHECKPOINTS[1:]:
        if checkpoint > comparison.n_atomic:
            return checkpoint
    return CHECKPOINTS[-1]
