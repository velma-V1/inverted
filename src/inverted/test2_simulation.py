from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations, permutations
import math
from typing import Any

from .oracle import evaluate_task
from .system_executor import generate_candidate
from .tasks import generate_task
from .test2_analysis import (
    OutcomeSnapshot,
    classify_transition,
    failure_kill_matrix,
    summarize_component_effects,
)


CAUSAL = "CAUSAL_REPLAY"
REQUIRES_NEW_INFERENCE = "REQUIRES_NEW_INFERENCE"

_COMPONENTS = (
    "requirement_validator",
    "retry",
    "targeted_repair",
    "oracle_auditor",
    "final_validator",
)
_PROGRESSIVE_ORDER = _COMPONENTS
_SLICE_DIMENSIONS = (
    ("family",),
    ("complexity",),
    ("quality",),
    ("family", "complexity"),
    ("family", "quality"),
    ("complexity", "quality"),
    ("family", "complexity", "quality"),
)


def analyze_orderings(
    components: tuple[str, ...],
    prompt_changing_components: set[str] | None = None,
) -> list[dict[str, Any]]:
    prompt_changing_components = set(prompt_changing_components or set())
    out = []
    for order in permutations(components):
        changes_upstream_prompt = any(
            component in prompt_changing_components and index < len(order) - 1
            for index, component in enumerate(order)
        )
        out.append({
            "order": " -> ".join(order),
            "components": list(order),
            "changes_upstream_prompt": changes_upstream_prompt,
            "causal_status": REQUIRES_NEW_INFERENCE if changes_upstream_prompt else CAUSAL,
        })
    return out


def _snapshot(task: Any, candidate: Any, *, blocked: bool = False) -> OutcomeSnapshot:
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    fault = candidate.injected_faults[0] if candidate.injected_faults else None
    return OutcomeSnapshot(
        success=bool(oracle.success and not blocked),
        catastrophic=bool(oracle.catastrophic and not blocked),
        blocked=blocked,
        failure_signature=None if oracle.success else (fault or ",".join(oracle.failed_requirement_ids) or "unknown"),
    )


def _cell(family: str, complexity: int, quality: float, seed: int, epoch: int) -> dict[str, Any]:
    task_seed = seed * 1009 + epoch * 9176 + complexity * 31
    task = generate_task(family, complexity, task_seed)
    candidates = [
        generate_candidate(task, quality, seed * 100000 + epoch * 1000 + complexity * 100 + attempt)
        for attempt in range(3)
    ]
    outcomes = [_snapshot(task, candidate) for candidate in candidates]
    perfect = generate_candidate(task, 1.0, seed * 700001 + epoch * 97 + complexity)
    return {
        "task": task,
        "candidates": candidates,
        "outcomes": outcomes,
        "perfect": perfect,
        "id": f"mf-{family}-L{complexity}-q{quality:.2f}-s{seed}-e{epoch}",
        "family": family,
        "complexity": complexity,
        "quality": quality,
        "seed": seed,
        "epoch": epoch,
    }


def _blocked_from(current: OutcomeSnapshot) -> OutcomeSnapshot:
    return OutcomeSnapshot(
        success=False,
        catastrophic=False,
        blocked=True,
        failure_signature=current.failure_signature,
    )


def _outcome_for_order(
    cell: dict[str, Any], order: tuple[str, ...]
) -> tuple[OutcomeSnapshot, str | None, list[dict[str, Any]]]:
    outcomes: list[OutcomeSnapshot] = cell["outcomes"]
    current = outcomes[0]
    candidate_index = 0
    first_defense: str | None = None
    trace: list[dict[str, Any]] = []

    for step, component in enumerate(order, start=1):
        before = current
        terminal = False

        if component == "requirement_validator":
            if not current.success:
                first_defense = first_defense or "validator"
                current = _blocked_from(current)

        elif component == "retry":
            if not current.success and candidate_index + 1 < len(outcomes):
                candidate_index += 1
                current = outcomes[candidate_index]

        elif component == "targeted_repair":
            if not current.success:
                first_defense = first_defense or "repair"
                current = _snapshot(cell["task"], cell["perfect"])

        elif component == "oracle_auditor":
            if not current.success:
                first_defense = first_defense or "auditor"
                current = _blocked_from(current)

        elif component == "final_validator":
            if not current.success:
                first_defense = first_defense or "final_validator"
                current = _blocked_from(current)
                terminal = True

        else:
            raise ValueError(f"unknown Test-2 component: {component}")

        trace.append({
            "step": step,
            "component": component,
            "before_success": before.success,
            "before_blocked": before.blocked,
            "after_success": current.success,
            "after_blocked": current.blocked,
            "transition": classify_transition(before, current),
            "candidate_index": candidate_index,
            "terminal": terminal,
        })
        if terminal:
            break

    return current, first_defense, trace


def _outcome_for_components(
    cell: dict[str, Any], components: tuple[str, ...]
) -> tuple[OutcomeSnapshot, str | None]:
    outcome, defense, _ = _outcome_for_order(cell, components)
    return outcome, defense


def _effect_row(name: str, before: list[OutcomeSnapshot], after: list[OutcomeSnapshot]) -> dict[str, Any]:
    summary = summarize_component_effects(zip(before, after))
    n = len(after)
    successes = sum(x.success for x in after)
    return {
        "component": name,
        "n": n,
        "successes": successes,
        "success_rate": successes / n if n else 0.0,
        "blocked": sum(x.blocked for x in after),
        "catastrophic": sum(x.catastrophic for x in after),
        **{key: value for key, value in summary.items() if key != "transitions"},
    }


def _slice_values(cell: dict[str, Any], dimensions: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(cell[dimension] for dimension in dimensions)


def _slice_identity(dimensions: tuple[str, ...], values: tuple[Any, ...]) -> dict[str, Any]:
    row: dict[str, Any] = {"slice_type": "_".join(dimensions)}
    for dimension, value in zip(dimensions, values):
        row[dimension] = value
    return row


def _component_slice_effects(
    cells: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for comparison in comparisons:
        before: list[OutcomeSnapshot] = comparison["before"]
        after: list[OutcomeSnapshot] = comparison["after"]
        for dimensions in _SLICE_DIMENSIONS:
            grouped: dict[tuple[Any, ...], list[tuple[OutcomeSnapshot, OutcomeSnapshot]]] = defaultdict(list)
            for cell, a, b in zip(cells, before, after):
                grouped[_slice_values(cell, dimensions)].append((a, b))
            for values, pairs in grouped.items():
                n = len(pairs)
                before_successes = sum(a.success for a, _ in pairs)
                after_successes = sum(b.success for _, b in pairs)
                transitions = summarize_component_effects(pairs)
                row = {
                    **_slice_identity(dimensions, values),
                    "mode": comparison["mode"],
                    "component": comparison["component"],
                    "n": n,
                    "before_success_rate": before_successes / n if n else 0.0,
                    "success_rate": after_successes / n if n else 0.0,
                    "gain_pp": ((after_successes - before_successes) / n * 100.0) if n else 0.0,
                    "blocked_rate": sum(b.blocked for _, b in pairs) / n if n else 0.0,
                    "catastrophic_rate": sum(b.catastrophic for _, b in pairs) / n if n else 0.0,
                    "wins_created": transitions["wins_created"],
                    "wins_destroyed": transitions["wins_destroyed"],
                    "net_wins": transitions["net_wins"],
                    "failures_prevented": transitions["failures_prevented"],
                    "failures_displaced": transitions["failures_displaced"],
                    "catastrophics_removed": transitions["catastrophics_removed"],
                    "catastrophics_added": transitions["catastrophics_added"],
                }
                rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            str(row["mode"]), str(row["component"]), str(row["slice_type"]),
            str(row.get("family", "")), str(row.get("complexity", "")), str(row.get("quality", "")),
        ),
    )


def _rank_order_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row["slice_type"], row.get("family"), row.get("complexity"), row.get("quality")
        )
        groups[key].append(row)
    ranked: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda item: tuple(str(x) for x in item)):
        group = sorted(
            groups[key],
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


def _score_orders(
    cells: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata = analyze_orderings(
        _COMPONENTS,
        # Retry replays already-fixed candidates; targeted repair would create a
        # new model output and therefore invalidates downstream prompt replay.
        prompt_changing_components={"targeted_repair"},
    )
    scored: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    for meta in metadata:
        order = tuple(meta["components"])
        outcomes = [_outcome_for_order(cell, order)[0] for cell in cells]
        successes = sum(x.success for x in outcomes)
        blocked = sum(x.blocked for x in outcomes)
        catastrophic = sum(x.catastrophic for x in outcomes)
        scored.append({
            **meta,
            "n": len(outcomes),
            "successes": successes,
            "simulated_success_rate": successes / len(outcomes) if outcomes else 0.0,
            "blocked": blocked,
            "blocked_rate": blocked / len(outcomes) if outcomes else 0.0,
            "catastrophic": catastrophic,
            "catastrophic_rate": catastrophic / len(outcomes) if outcomes else 0.0,
        })
        for dimensions in _SLICE_DIMENSIONS:
            grouped: dict[tuple[Any, ...], list[OutcomeSnapshot]] = defaultdict(list)
            for cell, outcome in zip(cells, outcomes):
                grouped[_slice_values(cell, dimensions)].append(outcome)
            for values, group in grouped.items():
                n = len(group)
                slice_rows.append({
                    **_slice_identity(dimensions, values),
                    "order": meta["order"],
                    "components": meta["components"],
                    "causal_status": meta["causal_status"],
                    "changes_upstream_prompt": meta["changes_upstream_prompt"],
                    "n": n,
                    "simulated_success_rate": sum(x.success for x in group) / n if n else 0.0,
                    "blocked_rate": sum(x.blocked for x in group) / n if n else 0.0,
                    "catastrophic_rate": sum(x.catastrophic for x in group) / n if n else 0.0,
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
    return scored, ranking, _rank_order_slices(slice_rows)


def _binary_correlation(a: list[bool], b: list[bool]) -> float | None:
    if not a or len(a) != len(b):
        return None
    xa = [1.0 if x else 0.0 for x in a]
    xb = [1.0 if x else 0.0 for x in b]
    ma = sum(xa) / len(xa)
    mb = sum(xb) / len(xb)
    va = sum((x - ma) ** 2 for x in xa) / len(xa)
    vb = sum((x - mb) ** 2 for x in xb) / len(xb)
    if va <= 0.0 or vb <= 0.0:
        return None
    cov = sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / len(xa)
    return cov / math.sqrt(va * vb)


def _candidate_attempt_metadata(cells: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n = len(cells)
    attempts = [[bool(cell["outcomes"][index].success) for cell in cells] for index in range(3)]
    saturation: list[dict[str, Any]] = []
    prior_success = [False] * n
    for index in range(3):
        current = attempts[index]
        new_recoveries = sum((not prior_success[i]) and current[i] for i in range(n))
        remaining_before = sum(not value for value in prior_success)
        cumulative = [prior_success[i] or current[i] for i in range(n)]
        saturation.append({
            "attempts_available": index + 1,
            "cumulative_successes": sum(cumulative),
            "cumulative_success_rate": sum(cumulative) / n if n else 0.0,
            "marginal_recoveries": new_recoveries,
            "marginal_gain_pp": new_recoveries / n * 100.0 if n else 0.0,
            "conditional_recovery_rate": new_recoveries / remaining_before if remaining_before else 0.0,
            "remaining_failures": sum(not value for value in cumulative),
        })
        prior_success = cumulative

    p = [sum(values) / n if n else 0.0 for values in attempts]
    observed_no_success = sum(not (a or b or c) for a, b, c in zip(*attempts)) / n if n else 0.0
    expected_no_success = math.prod(1.0 - value for value in p)
    independence = {
        "n": n,
        "attempt_1_success_rate": p[0],
        "attempt_2_success_rate": p[1],
        "attempt_3_success_rate": p[2],
        "observed_no_success_in_3_rate": observed_no_success,
        "independent_expected_no_success_in_3_rate": expected_no_success,
        "observed_to_independent_failure_ratio": (
            observed_no_success / expected_no_success if expected_no_success > 0 else None
        ),
        "success_correlation_attempt_1_2": _binary_correlation(attempts[0], attempts[1]),
        "success_correlation_attempt_1_3": _binary_correlation(attempts[0], attempts[2]),
        "success_correlation_attempt_2_3": _binary_correlation(attempts[1], attempts[2]),
    }
    return saturation, independence


def _base_cell_records(
    cells: list[dict[str, Any]], full_outcomes: list[OutcomeSnapshot]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell, full in zip(cells, full_outcomes):
        outcomes = cell["outcomes"]
        first_success = next((index + 1 for index, outcome in enumerate(outcomes) if outcome.success), None)
        row: dict[str, Any] = {
            "case_id": cell["id"],
            "family": cell["family"],
            "complexity": cell["complexity"],
            "quality": cell["quality"],
            "seed": cell["seed"],
            "epoch": cell["epoch"],
            "requirement_count": len(cell["task"].requirements),
            "first_success_attempt": first_success,
            "no_valid_candidate_in_3": first_success is None,
            "full_stack_success": full.success,
            "full_stack_blocked": full.blocked,
            "full_stack_catastrophic": full.catastrophic,
        }
        for index, outcome in enumerate(outcomes, start=1):
            candidate = cell["candidates"][index - 1]
            row.update({
                f"attempt_{index}_success": outcome.success,
                f"attempt_{index}_catastrophic": outcome.catastrophic,
                f"attempt_{index}_failure_signature": outcome.failure_signature,
                f"attempt_{index}_injected_faults": list(candidate.injected_faults),
            })
        rows.append(row)
    return rows


def _candidate_records(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        task = cell["task"]
        for attempt, candidate in enumerate(cell["candidates"], start=1):
            oracle = evaluate_task(task, candidate.state, candidate.actions)
            rows.append({
                "case_id": cell["id"],
                "family": cell["family"],
                "complexity": cell["complexity"],
                "quality": cell["quality"],
                "seed": cell["seed"],
                "epoch": cell["epoch"],
                "attempt": attempt,
                "candidate_id": candidate.id,
                "actions": [action.to_dict() for action in candidate.actions],
                "final_state": candidate.state.to_dict(),
                "injected_faults": list(candidate.injected_faults),
                "oracle_success": oracle.success,
                "catastrophic": oracle.catastrophic,
                "passed_requirement_ids": list(oracle.passed_requirement_ids),
                "failed_requirement_ids": list(oracle.failed_requirement_ids),
            })
    return rows


def _failure_recovery_matrix(
    cells: list[dict[str, Any]], baseline: list[OutcomeSnapshot], full_traces: list[list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for cell, before, trace in zip(cells, baseline, full_traces):
        if before.success:
            continue
        fault = before.failure_signature or "unknown"
        counter = grouped[fault]
        counter["total_failures"] += 1
        recovery = next(
            (item["component"] for item in trace if not item["before_success"] and item["after_success"]),
            None,
        )
        first_block = next(
            (item["component"] for item in trace if not item["before_blocked"] and item["after_blocked"]),
            None,
        )
        if first_block:
            counter[f"first_blocked_by_{first_block}"] += 1
        if recovery:
            counter[f"recovered_by_{recovery}"] += 1
        else:
            counter["unrecovered"] += 1
    columns = sorted({key for counter in grouped.values() for key in counter if key != "total_failures"})
    rows = []
    for fault, counter in sorted(grouped.items()):
        total = counter["total_failures"]
        row: dict[str, Any] = {"fault": fault, "total_failures": total}
        for column in columns:
            row[column] = counter[column]
            row[f"{column}_rate"] = counter[column] / total if total else 0.0
        rows.append(row)
    return rows


def run_model_free_atlas(seed_count: int = 10) -> dict[str, Any]:
    if seed_count <= 0:
        raise ValueError("seed_count must be positive")
    qualities = (0.20, 0.40, 0.60, 0.80, 0.95)
    cells = []
    for seed_index in range(seed_count):
        seed = 1001 + seed_index * 997
        for epoch in (0, 1):
            for family in ("state", "policy", "reconciliation"):
                for complexity in (1, 2, 3, 4):
                    for quality in qualities:
                        cells.append(_cell(family, complexity, quality, seed, epoch))

    baseline = [cell["outcomes"][0] for cell in cells]
    baseline_successes = sum(x.success for x in baseline)
    baseline_rate = baseline_successes / len(baseline)

    standalone_effects = []
    standalone_outcomes: dict[str, list[OutcomeSnapshot]] = {}
    for component in _COMPONENTS:
        after = [_outcome_for_components(cell, (component,))[0] for cell in cells]
        standalone_outcomes[component] = after
        standalone_effects.append(_effect_row(component, baseline, after))

    progressive_effects = []
    progressive_snapshots: dict[int, list[OutcomeSnapshot]] = {0: baseline}
    active: list[str] = []
    previous = baseline
    progressive_comparisons: list[dict[str, Any]] = []
    for step, component in enumerate(_PROGRESSIVE_ORDER, start=1):
        active.append(component)
        after = [_outcome_for_components(cell, tuple(active))[0] for cell in cells]
        row = _effect_row(component, previous, after)
        row.update({
            "step": step,
            "stack": " -> ".join(active),
            "cumulative_success_rate": sum(x.success for x in after) / len(after),
        })
        progressive_effects.append(row)
        progressive_comparisons.append({"mode": "progressive", "component": component, "before": previous, "after": after})
        progressive_snapshots[step] = after
        previous = after

    full_components = tuple(_PROGRESSIVE_ORDER)
    full_outcomes = [_outcome_for_components(cell, full_components)[0] for cell in cells]
    ablation_effects = []
    for removed in full_components:
        kept = tuple(component for component in full_components if component != removed)
        after = [_outcome_for_components(cell, kept)[0] for cell in cells]
        row = _effect_row(f"FULL_MINUS_{removed}", full_outcomes, after)
        row.update({"removed": removed, "stack": " -> ".join(kept)})
        ablation_effects.append(row)

    pairwise_interactions = []
    standalone_rate = {
        component: sum(x.success for x in outcomes) / len(outcomes)
        for component, outcomes in standalone_outcomes.items()
    }
    standalone_gain = {component: rate - baseline_rate for component, rate in standalone_rate.items()}
    for a, b in combinations(_COMPONENTS, 2):
        outcomes = [_outcome_for_components(cell, (a, b))[0] for cell in cells]
        rate = sum(x.success for x in outcomes) / len(outcomes)
        observed_gain = rate - baseline_rate
        expected_additive_gain = standalone_gain[a] + standalone_gain[b]
        interaction = observed_gain - expected_additive_gain
        best_single_rate = max(standalone_rate[a], standalone_rate[b])
        if rate + 0.01 < best_single_rate:
            classification = "INTERFERES"
        elif interaction > 0.01:
            classification = "SUPER_ADDITIVE"
        elif interaction < -0.01:
            classification = "SATURATION_OR_OVERLAP"
        else:
            classification = "ADDITIVE_OR_NEAR_INDEPENDENT"
        pairwise_interactions.append({
            "component_a": a,
            "component_b": b,
            "component_a_success_rate": standalone_rate[a],
            "component_b_success_rate": standalone_rate[b],
            "success_rate": rate,
            "observed_gain": observed_gain,
            "expected_additive_gain": expected_additive_gain,
            "interaction": interaction,
            "classification": classification,
        })

    kill_records = []
    transitions = []
    component_traces: list[dict[str, Any]] = []
    per_cell_traces: list[list[dict[str, Any]]] = []
    for cell, before, after in zip(cells, baseline, full_outcomes):
        _, caught_by, trace = _outcome_for_order(cell, full_components)
        per_cell_traces.append(trace)
        fault = before.failure_signature or "none"
        kill_records.append({"fault": fault, "caught_by": caught_by or ("escaped" if not after.success else "none")})
        transitions.append({
            "case_id": cell["id"],
            "family": cell["family"],
            "complexity": cell["complexity"],
            "quality": cell["quality"],
            "transition": classify_transition(before, after),
            "before_success": before.success,
            "after_success": after.success,
            "before_catastrophic": before.catastrophic,
            "after_catastrophic": after.catastrophic,
            "after_blocked": after.blocked,
        })
        for item in trace:
            component_traces.append({
                "case_id": cell["id"],
                "family": cell["family"],
                "complexity": cell["complexity"],
                "quality": cell["quality"],
                **item,
            })

    saturation = []
    previous_rate = None
    for step in sorted(progressive_snapshots):
        outcomes = progressive_snapshots[step]
        rate = sum(x.success for x in outcomes) / len(outcomes)
        saturation.append({
            "step": step,
            "stack": "BASELINE" if step == 0 else " -> ".join(_PROGRESSIVE_ORDER[:step]),
            "success_rate": rate,
            "marginal_gain": None if previous_rate is None else rate - previous_rate,
        })
        previous_rate = rate

    orderings, order_ranking, order_slice_ranking = _score_orders(cells)
    candidate_saturation, candidate_independence = _candidate_attempt_metadata(cells)

    standalone_comparisons = [
        {"mode": "standalone", "component": component, "before": baseline, "after": outcomes}
        for component, outcomes in standalone_outcomes.items()
    ]
    component_slice_effects = _component_slice_effects(
        cells, standalone_comparisons + progressive_comparisons
    )

    # Count simulated evaluation units, not inference calls.
    units_per_cell = 1 + len(_COMPONENTS) + len(_PROGRESSIVE_ORDER) + len(_COMPONENTS) + len(list(combinations(_COMPONENTS, 2))) + len(orderings)
    trial_units = len(cells) * units_per_cell
    return {
        "evidence_scope": "MODEL_FREE_DETERMINISTIC_ATLAS_NOT_LOCAL_MODEL_EVIDENCE",
        "base_cells": len(cells),
        "trial_units": trial_units,
        "baseline_successes": baseline_successes,
        "baseline_failures": len(baseline) - baseline_successes,
        "baseline_success_rate": baseline_rate,
        "full_successes": sum(x.success for x in full_outcomes),
        "full_success_rate": sum(x.success for x in full_outcomes) / len(full_outcomes),
        "standalone_effects": standalone_effects,
        "progressive_effects": progressive_effects,
        "ablation_effects": ablation_effects,
        "pairwise_interactions": pairwise_interactions,
        "failure_kill_matrix": failure_kill_matrix(kill_records),
        "failure_recovery_matrix": _failure_recovery_matrix(cells, baseline, per_cell_traces),
        "saturation": saturation,
        "candidate_saturation": candidate_saturation,
        "candidate_independence": candidate_independence,
        "orderings": orderings,
        "order_ranking": order_ranking,
        "order_slice_ranking": order_slice_ranking,
        "component_slice_effects": component_slice_effects,
        "outcome_transitions": transitions,
        "component_traces": component_traces,
        "base_cell_records": _base_cell_records(cells, full_outcomes),
        "candidate_records": _candidate_records(cells),
    }
