from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import fmean
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
    # Maximize success; minimize calls, latency and catastrophic rate when present.
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
    frontier = []
    for row in rows:
        if not any(other is not row and _dominates(other, row) for other in rows):
            frontier.append(row)
    return sorted(frontier, key=lambda row: (-float(row.get("success_rate", 0)), float(row.get("calls", 0)), str(row.get("name", ""))))


def model_complementarity(
    outcomes: dict[str, dict[str, bool]], model_a: str, model_b: str
) -> dict[str, Any]:
    counts = Counter()
    for task_id, by_model in outcomes.items():
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
        "error_overlap": (counts["both_fail"] / error_union) if error_union else 0.0,
        "complementarity": ((counts["a_only"] + counts["b_only"]) / n) if n else 0.0,
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
        "rows": rows,
    }


def _best_model_for_rows(rows: list[dict[str, Any]]) -> tuple[str | None, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["model"])] += int(bool(row.get("success")))
    if not counts:
        return None, 0
    model = sorted(counts, key=lambda m: (-counts[m], m))[0]
    return model, counts[model]


def derive_layered_router(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "best_single_model": {"model": None, "successes": 0},
            "best_static_role_assignment": {"successes": 0, "assignments": {}},
            "best_task_type_router": {"successes": 0, "assignments": {}},
            "oracle_per_task": {"successes": 0},
            "role_champions": {},
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
    type_successes = 0
    for key, group in sorted(type_groups.items()):
        model, _ = _best_model_for_rows(group)
        if model is None:
            continue
        encoded = f"{key[0]}|{key[1]}"
        type_assignments[encoded] = model
        type_successes += sum(
            int(bool(row.get("success"))) for row in group if str(row["model"]) == model
        )

    task_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        task_groups[str(row["task_id"])].append(row)
    oracle_successes = sum(any(bool(r.get("success")) for r in group) for group in task_groups.values())

    return {
        "best_single_model": {"model": best_single_model, "successes": best_single_successes},
        "best_static_role_assignment": {"successes": static_successes, "assignments": role_champions},
        "best_task_type_router": {"successes": type_successes, "assignments": type_assignments},
        "oracle_per_task": {"successes": int(oracle_successes)},
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
        key = tuple(row.get(dim) for dim in dimensions)
        groups[key].append(row)
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
