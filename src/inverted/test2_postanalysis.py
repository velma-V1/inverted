from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Iterable


def _mean(values: list[bool]) -> float:
    return sum(bool(value) for value in values) / len(values) if values else 0.0


def _binary_correlation(a: list[bool], b: list[bool]) -> float | None:
    if not a or len(a) != len(b):
        return None
    xa = [1.0 if value else 0.0 for value in a]
    xb = [1.0 if value else 0.0 for value in b]
    ma = sum(xa) / len(xa)
    mb = sum(xb) / len(xb)
    va = sum((value - ma) ** 2 for value in xa) / len(xa)
    vb = sum((value - mb) ** 2 for value in xb) / len(xb)
    if va <= 0.0 or vb <= 0.0:
        return None
    covariance = sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / len(xa)
    return covariance / math.sqrt(va * vb)


def _group_rows(
    rows: list[dict[str, Any]], dimensions: tuple[str, ...]
) -> Iterable[tuple[tuple[Any, ...], list[dict[str, Any]]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(dimension) for dimension in dimensions)].append(row)
    for key in sorted(groups, key=lambda value: tuple(str(item) for item in value)):
        yield key, groups[key]


def _identity(dimensions: tuple[str, ...], values: tuple[Any, ...]) -> dict[str, Any]:
    if not dimensions:
        return {"slice_type": "overall"}
    out: dict[str, Any] = {"slice_type": "_".join(dimensions)}
    out.update({dimension: value for dimension, value in zip(dimensions, values)})
    return out


def _independence_row(
    group: list[dict[str, Any]], dimensions: tuple[str, ...], values: tuple[Any, ...]
) -> dict[str, Any]:
    attempts = [
        [bool(row.get(f"attempt_{attempt}_success")) for row in group]
        for attempt in (1, 2, 3)
    ]
    rates = [_mean(values_) for values_ in attempts]
    all_fail = [not (a or b or c) for a, b, c in zip(*attempts)]
    observed = _mean(all_fail)
    expected = math.prod(1.0 - rate for rate in rates)
    return {
        **_identity(dimensions, values),
        "n": len(group),
        "attempt_1_success_rate": rates[0],
        "attempt_2_success_rate": rates[1],
        "attempt_3_success_rate": rates[2],
        "observed_no_success_in_3_rate": observed,
        "independent_expected_no_success_in_3_rate": expected,
        "observed_to_independent_failure_ratio": observed / expected if expected > 0.0 else None,
        "success_correlation_attempt_1_2": _binary_correlation(attempts[0], attempts[1]),
        "success_correlation_attempt_1_3": _binary_correlation(attempts[0], attempts[2]),
        "success_correlation_attempt_2_3": _binary_correlation(attempts[1], attempts[2]),
    }


def candidate_independence_strata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Measure candidate correlation within stable task/quality strata.

    The aggregate row is useful for operational forecasting, while the quality
    strata prevent latent mixture effects from being mistaken for per-task
    candidate correlation.
    """
    if not rows:
        return []
    dimensions = (
        (),
        ("quality",),
        ("family",),
        ("complexity",),
        ("requirement_count",),
        ("family", "complexity", "quality"),
    )
    out: list[dict[str, Any]] = []
    for dims in dimensions:
        if not dims:
            out.append(_independence_row(rows, (), ()))
            continue
        for values, group in _group_rows(rows, dims):
            out.append(_independence_row(group, dims, values))
    return out


def _threshold_row(
    group: list[dict[str, Any]],
    dimensions: tuple[str, ...],
    values: tuple[Any, ...],
    next_attempt: int,
) -> dict[str, Any]:
    if next_attempt == 2:
        eligible = [row for row in group if not bool(row.get("attempt_1_success"))]
        recovered = [row for row in eligible if bool(row.get("attempt_2_success"))]
    elif next_attempt == 3:
        eligible = [
            row for row in group
            if not bool(row.get("attempt_1_success")) and not bool(row.get("attempt_2_success"))
        ]
        recovered = [row for row in eligible if bool(row.get("attempt_3_success"))]
    else:
        raise ValueError("next_attempt must be 2 or 3")
    recovery_rate = len(recovered) / len(eligible) if eligible else 0.0
    return {
        **_identity(dimensions, values),
        "next_attempt": next_attempt,
        "eligible_failures": len(eligible),
        "blind_regeneration_recoveries": len(recovered),
        "blind_regeneration_recovery_rate": recovery_rate,
        "repair_break_even_recovery_rate": recovery_rate,
        "interpretation": (
            f"At equal per-call cost, targeted repair must recover more than {recovery_rate:.6%} "
            f"of these eligible failures to beat blind attempt {next_attempt}."
        ),
    }


def retry_repair_thresholds(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the empirical recovery rate a repair call must beat vs another draw."""
    if not rows:
        return []
    out: list[dict[str, Any]] = []
    for attempt in (2, 3):
        out.append(_threshold_row(rows, (), (), attempt))

    for dims in (("quality",), ("family",), ("complexity",), ("requirement_count",)):
        for values, group in _group_rows(rows, dims):
            for attempt in (2, 3):
                out.append(_threshold_row(group, dims, values, attempt))

    # Fault thresholds condition on the initial observed failure signature.
    failing = [row for row in rows if not bool(row.get("attempt_1_success"))]
    for values, group in _group_rows(failing, ("attempt_1_failure_signature",)):
        fault = values[0]
        for attempt in (2, 3):
            row = _threshold_row(group, (), (), attempt)
            row["slice_type"] = "fault"
            row["fault"] = fault
            out.append(row)
    return out
