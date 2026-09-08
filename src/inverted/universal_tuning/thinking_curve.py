from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .core import Observation


@dataclass(frozen=True)
class ThinkingBudgetPoint:
    thinking_budget: int
    n_observations: int
    success_rate: float
    failure_rate: float
    semantic_quality_mean: float
    contract_quality_mean: float
    completion_rate: float
    latency_s_mean: float
    output_tokens_mean: float
    thinking_tokens_mean: float
    failure_classes: dict[str, int]
    evidence_sufficient: bool


@dataclass(frozen=True)
class ThinkingCurveResult:
    status: str
    evidence_sufficient: bool
    points: tuple[ThinkingBudgetPoint, ...]
    minimum_effective_budget: int | None
    optimum_budget: int | None
    saturation_budget: int | None
    degradation_budget: int | None
    overthinking_detected: bool
    success_threshold: float
    min_observations_per_budget: int
    material_delta: float


def _mean(values: Iterable[float]) -> float:
    rows = tuple(float(value) for value in values)
    return sum(rows) / len(rows) if rows else 0.0


def _point(
    budget: int,
    rows: tuple[Observation, ...],
    *,
    min_observations_per_budget: int,
) -> ThinkingBudgetPoint:
    successes = tuple(
        bool(row.completed and row.semantic_pass and row.contract_pass)
        for row in rows
    )
    success_rate = sum(successes) / len(rows)
    failure_counts: Counter[str] = Counter()
    for row, success in zip(rows, successes):
        if success:
            continue
        failure_counts.update(item.value for item in row.failure_classes)

    return ThinkingBudgetPoint(
        thinking_budget=int(budget),
        n_observations=len(rows),
        success_rate=success_rate,
        failure_rate=1.0 - success_rate,
        semantic_quality_mean=_mean(row.semantic_quality for row in rows),
        contract_quality_mean=_mean(row.contract_quality for row in rows),
        completion_rate=_mean(float(row.completed) for row in rows),
        latency_s_mean=_mean(row.latency_s for row in rows),
        output_tokens_mean=_mean(row.output_tokens for row in rows),
        thinking_tokens_mean=_mean(row.thinking_tokens for row in rows),
        failure_classes=dict(sorted(failure_counts.items())),
        evidence_sufficient=len(rows) >= min_observations_per_budget,
    )


def analyze_thinking_curve(
    observations: Iterable[Observation],
    *,
    success_threshold: float = 0.80,
    min_observations_per_budget: int = 40,
    material_delta: float = 0.05,
) -> ThinkingCurveResult:
    """Characterize a thinking-budget response curve from existing observations only.

    This function is intentionally post-hoc: it has no runner, adapter, client, or
    scheduling dependency and therefore cannot issue model calls. Callers should
    pass a causally comparable observation slice (same task/profile conditions
    except for the thinking budget) when using the result for policy decisions.
    """
    if not 0.0 <= float(success_threshold) <= 1.0:
        raise ValueError("success_threshold must be between 0 and 1")
    if int(min_observations_per_budget) < 1:
        raise ValueError("min_observations_per_budget must be at least 1")
    if float(material_delta) < 0.0:
        raise ValueError("material_delta must be non-negative")

    grouped: dict[int, list[Observation]] = defaultdict(list)
    for observation in observations:
        if not isinstance(observation, Observation):
            raise TypeError("analyze_thinking_curve requires Observation values")
        grouped[int(observation.profile.thinking_budget)].append(observation)

    points = tuple(
        _point(
            budget,
            tuple(grouped[budget]),
            min_observations_per_budget=int(min_observations_per_budget),
        )
        for budget in sorted(grouped)
    )
    evidence_sufficient = bool(points) and all(
        point.evidence_sufficient for point in points
    )

    common = {
        "points": points,
        "success_threshold": float(success_threshold),
        "min_observations_per_budget": int(min_observations_per_budget),
        "material_delta": float(material_delta),
    }
    if not evidence_sufficient:
        return ThinkingCurveResult(
            status="INSUFFICIENT_EVIDENCE",
            evidence_sufficient=False,
            minimum_effective_budget=None,
            optimum_budget=None,
            saturation_budget=None,
            degradation_budget=None,
            overthinking_detected=False,
            **common,
        )

    effective = tuple(
        point for point in points if point.success_rate >= float(success_threshold)
    )
    if not effective:
        return ThinkingCurveResult(
            status="NO_EFFECTIVE_BUDGET",
            evidence_sufficient=True,
            minimum_effective_budget=None,
            optimum_budget=None,
            saturation_budget=None,
            degradation_budget=None,
            overthinking_detected=False,
            **common,
        )

    minimum_effective = min(point.thinking_budget for point in effective)
    optimum = max(
        effective,
        key=lambda point: (
            point.success_rate,
            point.semantic_quality_mean,
            point.contract_quality_mean,
            point.completion_rate,
            -point.latency_s_mean,
            -point.thinking_tokens_mean,
            -point.thinking_budget,
        ),
    )

    larger = tuple(
        point for point in points if point.thinking_budget > optimum.thinking_budget
    )
    saturation = next(
        (
            point
            for point in larger
            if abs(point.success_rate - optimum.success_rate) < float(material_delta)
        ),
        None,
    )
    degradation = next(
        (
            point
            for point in larger
            if optimum.success_rate - point.success_rate >= float(material_delta)
        ),
        None,
    )

    return ThinkingCurveResult(
        status="CHARACTERIZED",
        evidence_sufficient=True,
        minimum_effective_budget=minimum_effective,
        optimum_budget=optimum.thinking_budget,
        saturation_budget=None if saturation is None else saturation.thinking_budget,
        degradation_budget=None if degradation is None else degradation.thinking_budget,
        overthinking_detected=degradation is not None,
        **common,
    )
