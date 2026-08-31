from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Any, Iterable


@dataclass(frozen=True)
class OutcomeSnapshot:
    success: bool
    catastrophic: bool = False
    blocked: bool = False
    failure_signature: str | None = None


def classify_transition(before: OutcomeSnapshot, after: OutcomeSnapshot) -> str:
    if before.catastrophic and not after.catastrophic:
        return "CATASTROPHIC_TO_SAFE"
    if not before.catastrophic and after.catastrophic:
        return "SAFE_TO_CATASTROPHIC"
    if before.success and after.success:
        return "SUCCESS_TO_SUCCESS"
    if before.success and not after.success:
        return "SUCCESS_TO_FAIL"
    if not before.success and after.success:
        return "FAIL_TO_SUCCESS"
    if after.blocked and not before.blocked:
        return "FAIL_TO_BLOCKED"
    if before.failure_signature != after.failure_signature:
        return "FAIL_TO_DIFFERENT_FAIL"
    return "FAIL_TO_FAIL"


def summarize_component_effects(
    matched_pairs: Iterable[tuple[OutcomeSnapshot, OutcomeSnapshot]],
) -> dict[str, Any]:
    transitions = Counter(classify_transition(a, b) for a, b in matched_pairs)
    wins_created = transitions["FAIL_TO_SUCCESS"]
    wins_destroyed = transitions["SUCCESS_TO_FAIL"]
    return {
        "transitions": dict(sorted(transitions.items())),
        "wins_created": wins_created,
        "wins_destroyed": wins_destroyed,
        "net_wins": wins_created - wins_destroyed,
        "failures_repaired": wins_created,
        "failures_prevented": transitions["FAIL_TO_BLOCKED"],
        "failures_displaced": transitions["FAIL_TO_DIFFERENT_FAIL"],
        "catastrophics_removed": transitions["CATASTROPHIC_TO_SAFE"],
        "catastrophics_added": transitions["SAFE_TO_CATASTROPHIC"],
        "wins_preserved": transitions["SUCCESS_TO_SUCCESS"],
        "failures_unchanged": transitions["FAIL_TO_FAIL"],
    }


def threshold_analysis(
    *,
    n: int,
    baseline_successes: int,
    recoverable_failures: int,
    targets_pp: tuple[float, ...] = (1, 3, 5, 10),
) -> list[dict[str, Any]]:
    if n <= 0:
        raise ValueError("n must be positive")
    if not (0 <= baseline_successes <= n):
        raise ValueError("baseline_successes must be within 0..n")
    total_failures = n - baseline_successes
    if not (0 <= recoverable_failures <= total_failures):
        raise ValueError("recoverable_failures must be within remaining failures")
    max_gain_pp = 100.0 * recoverable_failures / n
    rows = []
    for target in targets_pp:
        required = math.ceil((float(target) / 100.0) * n - 1e-12)
        rows.append({
            "target_pp": target,
            "n": n,
            "baseline_successes": baseline_successes,
            "baseline_success_rate": baseline_successes / n,
            "remaining_failures": total_failures,
            "recoverable_failures": recoverable_failures,
            "required_net_recoveries": required,
            "required_fraction_of_remaining_failures": required / total_failures if total_failures else None,
            "required_fraction_of_recoverable_failures": required / recoverable_failures if recoverable_failures else None,
            "max_possible_gain_pp": max_gain_pp,
            "feasible": required <= recoverable_failures,
        })
    return rows


def minimum_sufficient_stack(
    stacks: list[dict[str, Any]],
    gaps: tuple[float, ...] = (0.005, 0.01, 0.02),
) -> dict[str, dict[str, Any] | None]:
    if not stacks:
        return {f"within_{gap:g}": None for gap in gaps}
    best = max(float(row["success_rate"]) for row in stacks)
    out: dict[str, dict[str, Any] | None] = {}
    for gap in gaps:
        eligible = [row for row in stacks if best - float(row["success_rate"]) <= gap + 1e-12]
        choice = min(
            eligible,
            key=lambda row: (
                int(row.get("components", 10**9)),
                -float(row["success_rate"]),
                str(row.get("name", "")),
            ),
        ) if eligible else None
        out[f"within_{gap:g}"] = choice
    return out


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    dims = [
        (float(a.get("success_rate", 0.0)), float(b.get("success_rate", 0.0)), "max"),
        (float(a.get("calls", 0.0)), float(b.get("calls", 0.0)), "min"),
        (float(a.get("latency_s", 0.0)), float(b.get("latency_s", 0.0)), "min"),
    ]
    if "catastrophic_rate" in a or "catastrophic_rate" in b:
        dims.append((float(a.get("catastrophic_rate", 0.0)), float(b.get("catastrophic_rate", 0.0)), "min"))
    no_worse = True
    strictly_better = False
    for av, bv, direction in dims:
        if direction == "max":
            no_worse &= av >= bv
            strictly_better |= av > bv
        else:
            no_worse &= av <= bv
            strictly_better |= av < bv
    return bool(no_worse and strictly_better)


def pareto_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier = [
        row for row in rows
        if not any(other is not row and _dominates(other, row) for other in rows)
    ]
    return sorted(frontier, key=lambda row: (-float(row.get("success_rate", 0)), float(row.get("calls", 0)), str(row.get("name", ""))))


def model_complementarity(
    outcomes: dict[str, dict[str, bool]], model_a: str, model_b: str
) -> dict[str, Any]:
    counts = Counter()
    for by_model in outcomes.values():
        a = bool(by_model.get(model_a, False))
        b = bool(by_model.get(model_b, False))
        if a and b:
            counts["both_success"] += 1
        elif a:
            counts["a_only"] += 1
        elif b:
            counts["b_only"] += 1
        else:
            counts["both_fail"] += 1
    n = sum(counts.values())
    error_union = counts["a_only"] + counts["b_only"] + counts["both_fail"]
    return {
        "model_a": model_a,
        "model_b": model_b,
        "n": n,
        "both_success": counts["both_success"],
        "a_only": counts["a_only"],
        "b_only": counts["b_only"],
        "both_fail": counts["both_fail"],
        "unique_wins": counts["a_only"] + counts["b_only"],
        "error_overlap": counts["both_fail"] / error_union if error_union else 0.0,
        "complementarity": (counts["a_only"] + counts["b_only"]) / n if n else 0.0,
    }


def router_regret(
    outcomes: dict[str, dict[str, bool]], routed_models: dict[str, str]
) -> dict[str, Any]:
    oracle = 0
    routed = 0
    rows = []
    for task_id in sorted(outcomes):
        by_model = outcomes[task_id]
        oracle_ok = any(bool(v) for v in by_model.values())
        chosen = routed_models.get(task_id)
        routed_ok = bool(by_model.get(chosen, False)) if chosen is not None else False
        oracle += int(oracle_ok)
        routed += int(routed_ok)
        rows.append({
            "task_id": task_id,
            "chosen_model": chosen,
            "routed_success": routed_ok,
            "oracle_success": oracle_ok,
            "regret": int(oracle_ok) - int(routed_ok),
        })
    return {
        "n": len(rows),
        "oracle_successes": oracle,
        "routed_successes": routed,
        "regret_successes": oracle - routed,
        "regret_rate": (oracle - routed) / len(rows) if rows else 0.0,
        "rows": rows,
    }


def _best_model_for_rows(rows: list[dict[str, Any]]) -> tuple[str | None, int]:
    counts: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for row in rows:
        model = str(row["model"])
        counts[model] += int(bool(row.get("success")))
        totals[model] += 1
    if not counts:
        return None, 0
    model = sorted(counts, key=lambda m: (-(counts[m] / totals[m]), -counts[m], m))[0]
    return model, counts[model]


def derive_layered_router(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "best_single_model": {"model": None, "successes": 0},
            "best_static_role_assignment": {"successes": 0, "assignments": {}},
            "best_task_type_router": {"successes": 0, "assignments": {}},
            "oracle_per_task": {"successes": 0},
            "task_type_router_regret_successes": 0,
            "role_champions": {},
            "task_type_regret_rows": [],
        }

    best_single_model, best_single_successes = _best_model_for_rows(rows)

    role_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        role_groups[str(row["role"])].append(row)
    role_champions: dict[str, str] = {}
    for role, group in role_groups.items():
        model, _ = _best_model_for_rows(group)
        if model is not None:
            role_champions[role] = model
    static_successes = sum(
        int(bool(row.get("success")))
        for row in rows
        if role_champions.get(str(row["role"])) == str(row["model"])
    )

    type_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        type_groups[(str(row["role"]), str(row.get("family", "")))].append(row)
    type_assignments: dict[str, str] = {}
    for key, group in sorted(type_groups.items()):
        model, _ = _best_model_for_rows(group)
        if model is not None:
            type_assignments[f"{key[0]}|{key[1]}"] = model

    task_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        task_groups[str(row["task_id"])].append(row)
    oracle_successes = 0
    type_successes = 0
    regret_rows = []
    for task_id, group in sorted(task_groups.items()):
        oracle_ok = any(bool(r.get("success")) for r in group)
        exemplar = group[0]
        key = f"{exemplar.get('role', '')}|{exemplar.get('family', '')}"
        chosen = type_assignments.get(key)
        chosen_rows = [r for r in group if str(r.get("model")) == chosen]
        routed_ok = any(bool(r.get("success")) for r in chosen_rows)
        oracle_successes += int(oracle_ok)
        type_successes += int(routed_ok)
        regret_rows.append({
            "task_id": task_id,
            "role": exemplar.get("role"),
            "family": exemplar.get("family"),
            "chosen_model": chosen,
            "routed_success": routed_ok,
            "oracle_success": oracle_ok,
            "regret": int(oracle_ok) - int(routed_ok),
        })

    return {
        "best_single_model": {"model": best_single_model, "successes": best_single_successes},
        "best_static_role_assignment": {"successes": static_successes, "assignments": role_champions},
        "best_task_type_router": {"successes": type_successes, "assignments": type_assignments},
        "oracle_per_task": {"successes": oracle_successes},
        "task_type_router_regret_successes": oracle_successes - type_successes,
        "task_type_router_regret_rate": (oracle_successes - type_successes) / len(task_groups) if task_groups else 0.0,
        "task_type_regret_rows": regret_rows,
        "role_champions": role_champions,
    }


def failure_kill_matrix(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stages = ("formalizer", "executor", "validator", "repair", "revalidation", "auditor", "final_validator", "escaped")
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        grouped[str(row.get("fault", "unknown"))][str(row.get("caught_by", "escaped"))] += 1
    out = []
    for fault, counter in sorted(grouped.items()):
        total = sum(counter.values())
        item: dict[str, Any] = {"fault": fault, "total": total}
        for stage in stages:
            item[stage] = counter[stage]
            item[f"{stage}_rate"] = counter[stage] / total if total else 0.0
        out.append(item)
    return out


def capability_matrix(rows: list[dict[str, Any]], dimensions: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(dim) for dim in dimensions)].append(row)
    out = []
    for key, group in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        n = len(group)
        successes = sum(bool(r.get("success")) for r in group)
        item = {dim: value for dim, value in zip(dimensions, key)}
        item.update({"n": n, "successes": successes, "success_rate": successes / n if n else 0.0})
        out.append(item)
    return out


def residual_bottlenecks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = [row for row in rows if not bool(row.get("success"))]
    counts = Counter(str(row.get("failure_class") or row.get("fault") or "unknown") for row in failures)
    total = len(rows)
    return [
        {
            "failure_class": failure,
            "count": count,
            "fraction_of_all_cases": count / total if total else 0.0,
            "perfect_component_ceiling_gain": count / total if total else 0.0,
        }
        for failure, count in counts.most_common()
    ]


def saturation_curve(rows: list[dict[str, Any]], step_field: str = "step") -> list[dict[str, Any]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[int(row[step_field])].append(row)
    out = []
    previous_rate = None
    for step in sorted(groups):
        group = groups[step]
        rate = sum(bool(r.get("success")) for r in group) / len(group) if group else 0.0
        out.append({
            "step": step,
            "n": len(group),
            "success_rate": rate,
            "marginal_gain": None if previous_rate is None else rate - previous_rate,
        })
        previous_rate = rate
    return out
