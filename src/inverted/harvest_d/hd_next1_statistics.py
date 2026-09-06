from __future__ import annotations

import math
from typing import Sequence

from .types import SequentialDecision


def _binom_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i)) for i in range(k + 1))


def clopper_pearson_upper(k: int, n: int, alpha: float = 0.05) -> float:
    if n <= 0 or not 0 <= k <= n or not 0.0 < alpha < 1.0:
        raise ValueError("invalid exact-binomial inputs")
    if k == n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(120):
        mid = (lo + hi) / 2.0
        if _binom_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def exact_noninferiority_pvalue(k: int, n: int, margin: float) -> float:
    if n <= 0 or not 0 <= k <= n or not 0.0 < margin < 1.0:
        raise ValueError("invalid noninferiority inputs")
    return _binom_cdf(k, n, margin)


def holm_rejections(pvalues: Sequence[float], family_alpha: float = 0.05) -> tuple[bool, ...]:
    if not pvalues or not 0.0 < family_alpha < 1.0:
        raise ValueError("invalid Holm family")
    values = [float(value) for value in pvalues]
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("p-values must be in [0,1]")
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    result = [False] * len(values)
    active = True
    m = len(values)
    for rank, (index, value) in enumerate(ordered):
        threshold = family_alpha / (m - rank)
        if active and value <= threshold:
            result[index] = True
        else:
            active = False
    return tuple(result)


def noninferiority_family_decisions(
    loss_counts: Sequence[int],
    matched_ns: Sequence[int],
    *,
    margin: float = 0.05,
    family_alpha: float = 0.05,
) -> tuple[SequentialDecision, ...]:
    if len(loss_counts) != len(matched_ns) or not loss_counts:
        raise ValueError("matched loss-count and sample-size vectors are required")
    pvalues = [
        exact_noninferiority_pvalue(int(loss), int(n), float(margin))
        for loss, n in zip(loss_counts, matched_ns)
    ]
    rejected = holm_rejections(pvalues, family_alpha)
    return tuple(
        SequentialDecision.NONINFERIOR if ok else SequentialDecision.UNRESOLVED
        for ok in rejected
    )
