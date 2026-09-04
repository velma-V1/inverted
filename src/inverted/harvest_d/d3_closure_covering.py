from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import random
from typing import Callable, Mapping


@dataclass(frozen=True)
class CoveringRequirement:
    factors: tuple[str, ...]
    levels: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.factors or len(self.factors) != len(self.levels):
            raise ValueError("covering requirement must pair every factor with one level")


@dataclass(frozen=True)
class PairwiseCoverage:
    covered_pairs: int
    coverable_pairs: int
    missing_pairs: tuple[tuple[str, str, str, str], ...]

    @property
    def ratio(self) -> float:
        if self.coverable_pairs == 0:
            return 1.0
        return self.covered_pairs / self.coverable_pairs


@dataclass(frozen=True)
class CoveringDesign:
    rows: tuple[dict[str, str], ...]
    required_tuples: tuple[CoveringRequirement, ...]


def _pair_obligations(factors: Mapping[str, tuple[str, ...]]) -> set[tuple[str, str, str, str]]:
    obligations: set[tuple[str, str, str, str]] = set()
    names = tuple(factors)
    for left, right in combinations(names, 2):
        for left_level in factors[left]:
            for right_level in factors[right]:
                obligations.add((left, left_level, right, right_level))
    return obligations


def _covered_by_row(
    row: Mapping[str, str],
    factor_order: tuple[str, ...],
) -> set[tuple[str, str, str, str]]:
    return {
        (left, row[left], right, row[right])
        for left, right in combinations(factor_order, 2)
    }


def measure_pairwise_coverage(
    rows: tuple[dict[str, str], ...],
    factors: Mapping[str, tuple[str, ...]],
) -> PairwiseCoverage:
    expected = _pair_obligations(factors)
    factor_order = tuple(factors)
    observed: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if set(row) != set(factor_order):
            raise ValueError("covering row does not contain exactly the declared factors")
        observed |= _covered_by_row(row, factor_order)
    missing = tuple(sorted(expected - observed))
    return PairwiseCoverage(
        covered_pairs=len(expected) - len(missing),
        coverable_pairs=len(expected),
        missing_pairs=missing,
    )


def _requirement_satisfied(row: Mapping[str, str], requirement: CoveringRequirement) -> bool:
    return all(row.get(factor) == level for factor, level in zip(requirement.factors, requirement.levels))


def _validate_factors(factors: Mapping[str, tuple[str, ...]]) -> None:
    if len(factors) < 2:
        raise ValueError("covering design requires at least two factors")
    for name, levels in factors.items():
        if not name or not levels or len(set(levels)) != len(levels):
            raise ValueError(f"invalid covering factor: {name}")


def generate_covering_design(
    factors: Mapping[str, tuple[str, ...]],
    *,
    seed: int,
    required_tuples: tuple[CoveringRequirement, ...] = (),
    row_is_legal: Callable[[Mapping[str, str]], bool] | None = None,
) -> CoveringDesign:
    """Build a deterministic greedy mixed-level pairwise covering design.

    The algorithm operates on pair obligations, not the full Cartesian product.
    It greedily seeds a row from an uncovered pair, then chooses each remaining
    factor level to maximize newly covered obligations against already assigned
    values. A deterministic seeded tie order prevents platform-dependent output.
    """

    _validate_factors(factors)
    names = tuple(factors)
    index = {name: position for position, name in enumerate(names)}
    legal = row_is_legal or (lambda row: True)
    rng = random.Random(int(seed))
    tie_rank: dict[tuple[str, str], float] = {
        (name, level): rng.random()
        for name in names
        for level in factors[name]
    }

    uncovered = _pair_obligations(factors)
    rows: list[dict[str, str]] = []

    def choose_level(name: str, partial: Mapping[str, str]) -> str:
        scored: list[tuple[int, float, str]] = []
        for level in factors[name]:
            gain = 0
            for other, other_level in partial.items():
                if index[other] < index[name]:
                    pair = (other, other_level, name, level)
                else:
                    pair = (name, level, other, other_level)
                if pair in uncovered:
                    gain += 1
            scored.append((gain, -tie_rank[(name, level)], level))
        scored.sort(reverse=True)
        return scored[0][2]

    guard = 0
    while uncovered:
        guard += 1
        if guard > max(10000, len(uncovered) * 4):
            raise RuntimeError("covering design failed to converge")
        anchor = min(uncovered)
        left, left_level, right, right_level = anchor
        partial: dict[str, str] = {left: left_level, right: right_level}
        for name in names:
            if name not in partial:
                partial[name] = choose_level(name, partial)
        row = {name: partial[name] for name in names}

        if not legal(row):
            # Deterministically search single-coordinate repairs before failing.
            repaired = False
            for name in names:
                original = row[name]
                for level in factors[name]:
                    if level == original:
                        continue
                    candidate = dict(row)
                    candidate[name] = level
                    if legal(candidate):
                        row = candidate
                        repaired = True
                        break
                if repaired:
                    break
            if not repaired:
                raise ValueError(f"no legal covering row found for obligation {anchor}")

        covered = _covered_by_row(row, names) & uncovered
        if not covered:
            raise RuntimeError(f"covering row made no progress for obligation {anchor}")
        rows.append(row)
        uncovered -= covered

    for requirement in required_tuples:
        if any(_requirement_satisfied(row, requirement) for row in rows):
            continue
        for factor, level in zip(requirement.factors, requirement.levels):
            if factor not in factors or level not in factors[factor]:
                raise ValueError(f"required tuple references invalid level: {factor}={level}")
        row = {name: factors[name][0] for name in names}
        for factor, level in zip(requirement.factors, requirement.levels):
            row[factor] = level
        if not legal(row):
            raise ValueError(f"required tuple cannot be represented by a legal row: {requirement}")
        rows.append(row)

    # Remove exact duplicate rows while preserving deterministic order.
    unique: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for row in rows:
        key = tuple((name, row[name]) for name in names)
        if key not in seen:
            seen.add(key)
            unique.append(row)

    coverage = measure_pairwise_coverage(tuple(unique), factors)
    if coverage.ratio != 1.0:
        raise RuntimeError(f"covering design incomplete: {len(coverage.missing_pairs)} pair obligations missing")

    return CoveringDesign(tuple(unique), tuple(required_tuples))
