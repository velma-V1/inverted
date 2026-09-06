"""Seeded, residency-safe ordering for frozen campaign units."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import random
from typing import Iterable


@dataclass(frozen=True)
class ScheduledUnit:
    unit_id: str
    model_key: str
    case_id: str
    treatment_id: str
    replicate: int
    execution_position: int | None = None
    selection_reason: str = "calibration_coverage"
    model_block: str | None = None
    planned_load_state: str | None = None
    protected_exploration: bool = False


def schedule_model_blocks(
    units: Iterable[ScheduledUnit], *, seed: int, protected_fraction: float = 0.20
) -> tuple[ScheduledUnit, ...]:
    """Group by model, then randomize each model block with a reproducible seed.

    Model block order follows first appearance, preserving a caller's frozen
    model allocation. No unit is filtered for runtime cost.
    """
    if not 0.0 <= float(protected_fraction) <= 1.0:
        raise ValueError("protected_fraction must be between 0 and 1")
    rows = list(units)
    if any(not isinstance(row, ScheduledUnit) for row in rows):
        raise TypeError("units must contain ScheduledUnit values")
    grouped: dict[str, list[ScheduledUnit]] = {}
    for row in rows:
        grouped.setdefault(row.model_key, []).append(row)
    rng = random.Random(int(seed))
    scheduled: list[ScheduledUnit] = []
    for block_index, (model_key, block) in enumerate(grouped.items(), start=1):
        tie_break = {id(row): rng.random() for row in block}
        remaining = list(block)
        shuffled: list[ScheduledUnit] = []
        counts = {field: {} for field in ("case_id", "treatment_id", "replicate")}
        while remaining:
            def score(row: ScheduledUnit) -> tuple[int, int, int, float]:
                return tuple(
                    counts[field].get(getattr(row, field), 0)
                    for field in ("case_id", "treatment_id", "replicate")
                ) + (tie_break[id(row)],)

            chosen = min(remaining, key=score)
            remaining.remove(chosen)
            shuffled.append(chosen)
            for field in counts:
                value = getattr(chosen, field)
                counts[field][value] = counts[field].get(value, 0) + 1
        protected_count = math.ceil(len(shuffled) * protected_fraction)
        block_name = f"{model_key}-block-{block_index}"
        for offset, row in enumerate(shuffled):
            protected = offset < protected_count
            reason = "protected_exploration" if protected else row.selection_reason
            state = "planned_cold_or_load" if offset == 0 else "planned_warm_or_resident"
            scheduled.append(
                replace(
                    row,
                    execution_position=len(scheduled) + 1,
                    selection_reason=reason,
                    model_block=block_name,
                    planned_load_state=state,
                    protected_exploration=protected,
                )
            )
    return tuple(scheduled)
