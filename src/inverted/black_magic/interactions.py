from __future__ import annotations

from itertools import combinations, product
from typing import Any, Iterable


def generate_pairwise_covering_rows(factors: dict[str, list[Any]]) -> list[dict[str, Any]]:
    names = tuple(factors)
    if not names:
        return []
    return [dict(zip(names, values)) for values in product(*(factors[name] for name in names))]


def verify_t_way_coverage(
    rows: Iterable[dict[str, Any]],
    factors: dict[str, list[Any]],
    strength: int,
) -> dict[str, Any]:
    materialized = [dict(row) for row in rows]
    names = tuple(factors)
    strength = int(strength)
    if strength <= 0 or strength > len(names):
        raise ValueError("strength must be between 1 and number of factors")
    missing: list[dict[str, Any]] = []
    expected_count = 0
    for selected in combinations(names, strength):
        for values in product(*(factors[name] for name in selected)):
            expected_count += 1
            expected = dict(zip(selected, values))
            if not any(all(row.get(k) == v for k, v in expected.items()) for row in materialized):
                missing.append(expected)
    return {
        "strength": strength,
        "row_count": len(materialized),
        "expected_combinations": expected_count,
        "missing": missing,
        "complete": not missing,
    }


def verify_ordered_sequence_coverage(
    sequences: Iterable[Iterable[str]],
    required_relations: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    materialized = [list(sequence) for sequence in sequences]
    missing: list[list[str]] = []
    for before, after in required_relations:
        covered = False
        for sequence in materialized:
            if before in sequence and after in sequence and sequence.index(before) < sequence.index(after):
                covered = True
                break
        if not covered:
            missing.append([before, after])
    return {"sequence_count": len(materialized), "missing": missing, "complete": not missing}
