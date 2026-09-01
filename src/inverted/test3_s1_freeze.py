from __future__ import annotations

import json
import random
from itertools import permutations
from typing import Any, Iterable


ANALYSIS_ONLY_COMPONENTS = frozenset({"oracle_auditor"})
PRODUCTION_ORDER_RANKING_FILE = "order/order-ranking-production.csv"
DEFAULT_S1_PHYSICAL_CALL_CEILING = 80
DEFAULT_S1_FIXED_ORDER_COUNT = 2
DEFAULT_S1_SEED = 20260901


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "passed", "success"}:
        return True
    if text in {"false", "0", "no", "fail", "failed"}:
        return False
    return None


def _parse_components(value: Any, order: str) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.startswith("["):
            try:
                decoded = json.loads(text)
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            except json.JSONDecodeError:
                pass
    return [item.strip() for item in order.split("->") if item.strip()]


def _rank_key(row: dict[str, Any]) -> tuple[int, float, str]:
    rank = _as_int(row.get("rank"))
    success = _as_float(row.get("simulated_success_rate"))
    return (
        rank if rank is not None else 10**9,
        -(success if success is not None else -1.0),
        str(row.get("source_id") or ""),
    )


def derive_s1_order_candidates(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build S1 hypotheses only from the separate production-order atlas.

    The original `order/order-ranking.csv` remains preserved analysis-ceiling
    evidence because every Test-2 order in that file includes `oracle_auditor`.
    It is intentionally ignored here rather than stripping oracle from an
    already oracle-scored result.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        source_file = str(row.get("source_file") or "").replace("\\", "/")
        order = str(row.get("order") or "").strip()
        if not source_file.endswith(PRODUCTION_ORDER_RANKING_FILE) or not order:
            continue
        grouped.setdefault(order, []).append(row)

    out: list[dict[str, Any]] = []
    for order, observations in grouped.items():
        ordered = sorted(observations, key=_rank_key)
        primary = ordered[0]
        source_ids = sorted({str(row.get("source_id") or "") for row in observations})
        components = _parse_components(primary.get("components"), order)
        analysis_only = sorted(set(components).intersection(ANALYSIS_ONLY_COMPONENTS))
        ranks = [value for value in (_as_int(row.get("rank")) for row in observations) if value is not None]
        causal_statuses = sorted({str(row.get("causal_status")) for row in observations if row.get("causal_status")})
        causal_status = causal_statuses[0] if len(causal_statuses) == 1 else "MIXED" if causal_statuses else None
        row_count_values = [value for value in (_as_int(row.get("n")) for row in observations) if value is not None]
        declared_production = _as_bool(primary.get("production_eligible"))
        production_eligible = not analysis_only and declared_production is not False

        out.append({
            "candidate": order,
            "rank": min(ranks) if ranks else None,
            "components": components,
            "source_id": str(primary.get("source_id") or ""),
            "source_ids": source_ids,
            "source_count": len(source_ids),
            "source_file": str(primary.get("source_file") or "").replace("\\", "/"),
            "causal_status": causal_status,
            "causal_status_observations": causal_statuses,
            "changes_upstream_prompt": _as_bool(primary.get("changes_upstream_prompt")),
            "rows": max(row_count_values) if row_count_values else None,
            "simulated_success_rate": _as_float(primary.get("simulated_success_rate")),
            "simulated_blocked_rate": _as_float(primary.get("blocked_rate")),
            "simulated_catastrophe_rate": _as_float(primary.get("catastrophic_rate")),
            "verified_successes": None,
            "verified_failures": None,
            "verified_success_rate": None,
            "catastrophe_rate": None,
            "calls": None,
            "tokens": None,
            "latency_ms": None,
            "fully_costed": False,
            "production_eligible": production_eligible,
            "analysis_only_components": analysis_only,
            "exclusion_reason": (
                "contains analysis-only component(s): " + ", ".join(analysis_only)
                if analysis_only else "" if production_eligible else "production atlas marked row ineligible"
            ),
            "evidence_scope": primary.get("evidence_scope") or "PRODUCTION_ORDER_HYPOTHESIS",
            "evidence_basis": "MODEL_FREE_PRODUCTION_ORDER_RANKING_HYPOTHESIS",
            "tier_a_architecture_claim": False,
        })

    return sorted(
        out,
        key=lambda row: (
            row["rank"] if row["rank"] is not None else 10**9,
            -(row["simulated_success_rate"] if row["simulated_success_rate"] is not None else -1.0),
            row["candidate"],
        ),
    )


def select_s1_fixed_orders(
    candidates: Iterable[dict[str, Any]],
    *,
    count: int = DEFAULT_S1_FIXED_ORDER_COUNT,
) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("count must be >= 1")
    eligible = [dict(row) for row in candidates if row.get("production_eligible") is not False]
    eligible.sort(
        key=lambda row: (
            _as_int(row.get("rank")) if _as_int(row.get("rank")) is not None else 10**9,
            -(_as_float(row.get("simulated_success_rate")) if _as_float(row.get("simulated_success_rate")) is not None else -1.0),
            str(row.get("candidate") or ""),
        )
    )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in eligible:
        name = str(row.get("candidate") or "")
        if not name or name in seen:
            continue
        selected.append(row)
        seen.add(name)
        if len(selected) == count:
            break
    return selected


def _random_control_order(selected: list[dict[str, Any]], seed: int) -> str:
    if not selected:
        return ""
    components = _parse_components(selected[0].get("components"), str(selected[0].get("candidate") or ""))
    components = [component for component in components if component not in ANALYSIS_ONLY_COMPONENTS]
    selected_names = {str(row.get("candidate") or "") for row in selected}
    options = sorted({
        " -> ".join(order)
        for order in permutations(components)
        if " -> ".join(order) not in selected_names
    })
    if not options:
        return " -> ".join(reversed(components))
    return random.Random(seed).choice(options)


def finalize_s1_preregistration(
    base: dict[str, Any],
    candidates: Iterable[dict[str, Any]],
    *,
    physical_call_ceiling: int = DEFAULT_S1_PHYSICAL_CALL_CEILING,
    fixed_order_count: int = DEFAULT_S1_FIXED_ORDER_COUNT,
    seed: int = DEFAULT_S1_SEED,
) -> dict[str, Any]:
    """Produce the final S1 screening arm freeze without authorizing inference."""
    result = dict(base)
    all_candidates = [dict(row) for row in candidates]
    eligible = [row for row in all_candidates if row.get("production_eligible") is not False]
    selected = select_s1_fixed_orders(eligible, count=fixed_order_count)

    result["fixed_policy_candidate_count"] = len(all_candidates)
    result["production_eligible_fixed_order_count"] = len(eligible)
    result["excluded_analysis_only_order_count"] = len(all_candidates) - len(eligible)
    result["fixed_policy_evidence_basis"] = ["MODEL_FREE_PRODUCTION_ORDER_RANKING_HYPOTHESIS"] if all_candidates else []
    result["tier_a_inference_authorized"] = False

    if len(selected) < fixed_order_count:
        result.update({
            "status": "S1_ARM_FREEZE_BLOCKED",
            "arm_freeze_ready": False,
            "arm_freeze_blocker": (
                f"Need {fixed_order_count} production-eligible unique fixed orders; found {len(selected)}."
            ),
            "exact_budget": None,
            "selected_fixed_orders": [str(row.get("candidate") or "") for row in selected],
        })
        return result

    arm_count = 2 + len(selected)
    if physical_call_ceiling <= 0 or physical_call_ceiling % arm_count != 0:
        raise ValueError("physical_call_ceiling must divide evenly across the frozen S1 arms")
    per_arm_cap = physical_call_ceiling // arm_count
    random_order = _random_control_order(selected, seed)
    power = dict(result.get("power_evidence") or {})
    full_power_clusters = _as_int(power.get("recommended_clusters"))

    arms = [
        {
            "arm_id": "S1-A0",
            "role": "best_single_model_baseline",
            "order": None,
            "selection_basis": "frozen Test-2 Tier-A best-single-model evidence",
            "physical_call_cap": per_arm_cap,
        },
        {
            "arm_id": "S1-A1",
            "role": "current_best_fixed_hybrid",
            "order": str(selected[0]["candidate"]),
            "selection_basis": "top production-only S0 fixed-order hypothesis",
            "physical_call_cap": per_arm_cap,
        },
        {
            "arm_id": "S1-A2",
            "role": "alternate_fixed_order",
            "order": str(selected[1]["candidate"]),
            "selection_basis": "second production-only S0 fixed-order hypothesis",
            "physical_call_cap": per_arm_cap,
        },
        {
            "arm_id": "S1-A3",
            "role": "random_order_negative_control",
            "order": random_order,
            "selection_basis": f"deterministic production-component permutation control; seed={seed}",
            "physical_call_cap": per_arm_cap,
        },
    ]

    result.update({
        "status": "S1_SCREEN_FROZEN_AWAITING_TIER_A_AUTHORIZATION",
        "arm_freeze_ready": True,
        "arm_freeze_blocker": None,
        "selected_fixed_orders": [str(row["candidate"]) for row in selected],
        "arms": arms,
        "arm_count": arm_count,
        "exact_budget": physical_call_ceiling,
        "budget_unit": "physical_model_calls",
        "physical_call_cap_per_arm": per_arm_cap,
        "budget_freeze_requires_human_review": False,
        "budget_strategy": "equal_physical_call_screen",
        "full_power_cluster_requirement": full_power_clusters,
        "screen_is_underpowered_for_target_effect": bool(
            full_power_clusters is not None and full_power_clusters > per_arm_cap
        ),
        "screening_interpretation": (
            "S0 estimates the cluster requirement for the configured target effect, but S1 retains the campaign's "
            "80-call design ceiling. Therefore S1 is a bounded fixed-order screen: a null result cannot rule out the "
            "configured small effect, while a large stable effect can justify additional fixed-topology work."
        ),
        "equalization": (
            "Each arm receives the same physical-call cap. Token-normalized comparisons are secondary where telemetry permits."
        ),
        "random_control_seed": seed,
        "no_outcome_dependent_early_stopping": True,
    })
    result.pop("arm_freeze_blocker", None)
    return result
