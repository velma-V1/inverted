from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .types import SequentialDecision


@dataclass(frozen=True)
class ConfidenceSequence:
    mean: float
    lower: float
    upper: float
    n: int
    alpha: float
    method: str
    bounds: tuple[float, float]


@dataclass(frozen=True)
class SequentialEvidence:
    interval: ConfidenceSequence
    decision: SequentialDecision
    margin: float
    hard_violation: bool = False
    futile: bool = False


def classify_sequential_interval(
    lower: float,
    upper: float,
    *,
    margin: float,
    hard_violation: bool = False,
    futile: bool = False,
) -> SequentialDecision:
    if hard_violation:
        return SequentialDecision.HARMFUL
    if futile:
        return SequentialDecision.FUTILE
    if lower > margin:
        return SequentialDecision.SUPERIOR
    if upper < -margin:
        return SequentialDecision.HARMFUL
    if lower > -margin:
        return SequentialDecision.NONINFERIOR
    return SequentialDecision.UNRESOLVED


def anytime_hoeffding_cs(values: Iterable[float], alpha: float = 0.05) -> ConfidenceSequence:
    """Time-uniform Hoeffding confidence sequence for bounded observations.

    D3 uses a summable union-bound spending schedule
    alpha_n = alpha * 6 / (pi^2 * n^2). Values may be Bernoulli-like [0,1]
    observations or matched deltas in [-1,1].
    """

    xs = [float(x) for x in values]
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if not xs:
        return ConfidenceSequence(
            mean=0.0,
            lower=-1.0,
            upper=1.0,
            n=0,
            alpha=float(alpha),
            method="ANYTIME_HOEFFDING_UNION_V1",
            bounds=(-1.0, 1.0),
        )
    if any(x < -1.0 or x > 1.0 for x in xs):
        raise ValueError("D3 confidence sequence expects values bounded in [-1,1]")

    matched_delta = any(x < 0.0 for x in xs)
    if matched_delta:
        transformed = [(x + 1.0) / 2.0 for x in xs]
        bounds = (-1.0, 1.0)
    else:
        transformed = xs
        bounds = (0.0, 1.0)

    n = len(transformed)
    alpha_n = float(alpha) * 6.0 / (math.pi**2 * n**2)
    half = math.sqrt(math.log(2.0 / alpha_n) / (2.0 * n))
    transformed_mean = sum(transformed) / n
    transformed_lower = max(0.0, transformed_mean - half)
    transformed_upper = min(1.0, transformed_mean + half)

    if matched_delta:
        mean = 2.0 * transformed_mean - 1.0
        lower = 2.0 * transformed_lower - 1.0
        upper = 2.0 * transformed_upper - 1.0
    else:
        mean = transformed_mean
        lower = transformed_lower
        upper = transformed_upper

    return ConfidenceSequence(
        mean=mean,
        lower=lower,
        upper=upper,
        n=n,
        alpha=float(alpha),
        method="ANYTIME_HOEFFDING_UNION_V1",
        bounds=bounds,
    )


def sequential_evidence(
    values: Iterable[float],
    *,
    margin: float,
    alpha: float = 0.05,
    hard_violation: bool = False,
    futile: bool = False,
) -> SequentialEvidence:
    interval = anytime_hoeffding_cs(values, alpha=alpha)
    if interval.n == 0:
        decision = SequentialDecision.HARMFUL if hard_violation else SequentialDecision.UNRESOLVED
    else:
        decision = classify_sequential_interval(
            interval.lower,
            interval.upper,
            margin=float(margin),
            hard_violation=hard_violation,
            futile=futile,
        )
    return SequentialEvidence(
        interval=interval,
        decision=decision,
        margin=float(margin),
        hard_violation=hard_violation,
        futile=futile,
    )
