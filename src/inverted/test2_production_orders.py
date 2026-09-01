from __future__ import annotations

from collections import defaultdict
from typing import Any

from .test2_simulation import (
    _cell,
    _outcome_for_order,
    analyze_orderings,
)


PRODUCTION_COMPONENTS = (
    "requirement_validator",
    "retry",
    "targeted_repair",
    "final_validator",
)

_SLICE_DIMENSIONS = (
    ("family",),
    ("complexity",),
    ("quality",),
    ("family", "complexity"),
    ("family", "quality"),
    ("complexity", "quality"),
    ("family", "complexity", "quality"),
)


def _cells(seed_count: int) -> list[dict[str, Any]]:
    if seed_count <= 0:
        raise ValueError("seed_count must be positive")
    qualities = (0.20, 0.40, 0.60, 0.80, 0.95)
    cells: list[dict[str, Any]] = []
    for seed_index in range(seed_count):
        seed = 1001 + seed_index * 997
        for epoch in (0, 1):
            for family in ("state", "policy", "reconciliation"):
                for complexity in (1, 2, 3, 4):
                    for quality in qualities:
                        cells.append(_cell(family, complexity, quality, seed, epoch))
    return cells


def _slice_key(cell: dict[str, Any], dimensions: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(cell[dimension] for dimension in dimensions)


def _slice_identity(dimensions: tuple[str, ...], values: tuple[Any, ...]) -> dict[str, Any]:
    row: dict[str, Any] = {"slice_type": "_".join(dimensions)}
    for dimension, value in zip(dimensions, values):
        row[dimension] = value
    return row


def _rank_slice_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["slice_type"], row.get("family"), row.get("complexity"), row.get("quality"))].append(row)
    ranked: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: tuple(str(value) for value in item)):
        group = sorted(
            grouped[key],
            key=lambda row: (
                -float(row["simulated_success_rate"]),
                float(row["catastrophic_rate"]),
                float(row["blocked_rate"]),
                str(row["order"]),
            ),
        )
        for rank, row in enumerate(group, start=1):
            ranked.append({**row, "rank_within_slice": rank})
    return ranked


def run_production_order_atlas(seed_count: int = 10) -> dict[str, Any]:
    """Score only deployable component permutations over the Test-2 deterministic cells.

    The original Test-2 five-component order atlas remains an analysis ceiling
    because it includes `oracle_auditor`. This production atlas is separate so
    oracle-derived outcomes can never nominate a production S1 fixed-order arm.
    """
    cells = _cells(seed_count)
    metadata = analyze_orderings(
        PRODUCTION_COMPONENTS,
        prompt_changing_components={"targeted_repair"},
    )
    scored: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    for meta in metadata:
        order = tuple(meta["components"])
        outcomes = [_outcome_for_order(cell, order)[0] for cell in cells]
        successes = sum(outcome.success for outcome in outcomes)
        blocked = sum(outcome.blocked for outcome in outcomes)
        catastrophic = sum(outcome.catastrophic for outcome in outcomes)
        common = {
            **meta,
            "n": len(outcomes),
            "successes": successes,
            "simulated_success_rate": successes / len(outcomes) if outcomes else 0.0,
            "blocked": blocked,
            "blocked_rate": blocked / len(outcomes) if outcomes else 0.0,
            "catastrophic": catastrophic,
            "catastrophic_rate": catastrophic / len(outcomes) if outcomes else 0.0,
            "production_eligible": True,
            "evidence_scope": "PRODUCTION_ORDER_HYPOTHESIS",
            "analysis_only_components": [],
        }
        scored.append(common)
        for dimensions in _SLICE_DIMENSIONS:
            groups: dict[tuple[Any, ...], list[Any]] = defaultdict(list)
            for cell, outcome in zip(cells, outcomes):
                groups[_slice_key(cell, dimensions)].append(outcome)
            for values, group in groups.items():
                n = len(group)
                slice_rows.append({
                    **_slice_identity(dimensions, values),
                    "order": meta["order"],
                    "components": meta["components"],
                    "causal_status": meta["causal_status"],
                    "changes_upstream_prompt": meta["changes_upstream_prompt"],
                    "n": n,
                    "simulated_success_rate": sum(outcome.success for outcome in group) / n if n else 0.0,
                    "blocked_rate": sum(outcome.blocked for outcome in group) / n if n else 0.0,
                    "catastrophic_rate": sum(outcome.catastrophic for outcome in group) / n if n else 0.0,
                    "production_eligible": True,
                    "evidence_scope": "PRODUCTION_ORDER_HYPOTHESIS",
                })

    ranking = sorted(
        scored,
        key=lambda row: (
            -float(row["simulated_success_rate"]),
            float(row["catastrophic_rate"]),
            float(row["blocked_rate"]),
            str(row["order"]),
        ),
    )
    ranking = [{"rank": index, **row} for index, row in enumerate(ranking, start=1)]
    return {
        "evidence_scope": "PRODUCTION_ORDER_HYPOTHESIS",
        "base_cells": len(cells),
        "trial_units": len(cells) * len(metadata),
        "components": list(PRODUCTION_COMPONENTS),
        "orderings": scored,
        "order_ranking": ranking,
        "order_slice_ranking": _rank_slice_rows(slice_rows),
    }
