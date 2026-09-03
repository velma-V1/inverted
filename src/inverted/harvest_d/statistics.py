from __future__ import annotations

from .types import SequentialDecision


def classify_sequential_interval(lower: float, upper: float, *, margin: float,
                                 hard_violation: bool = False, futile: bool = False) -> SequentialDecision:
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
