from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .test3_s2_cases import S2_HOLDOUT, S2_PROTOCOL_REVISION
from .test3_s2_policy import REAL_ARM_IDS
from .test3_s2_runtime import (
    S2_COMBINED_ACTION_BUDGET,
    S2_EXACT_BUDGET,
    S2_MATCHED_CASES,
    S2_PER_ARM_CALL_CAP,
    S2_TRIAL_COUNT,
)


def _summary_rows(rows: list[dict[str, Any]], dimensions: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(name) for name in dimensions)].append(row)
    out: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        successes = sum(bool(row.get("success")) for row in group)
        catastrophes = sum(bool(row.get("catastrophic")) for row in group)
        item = {name: value for name, value in zip(dimensions, key)}
        item.update({
            "trials": len(group),
            "successes": successes,
            "success_rate": successes / len(group) if group else 0.0,
            "catastrophes": catastrophes,
            "catastrophe_rate": catastrophes / len(group) if group else 0.0,
        })
        out.append(item)
    return out


def _pair(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]], *, a_id: str, b_id: str) -> dict[str, Any]:
    a = {str(row["task_id"]): row for row in a_rows}
    b = {str(row["task_id"]): row for row in b_rows}
    keys = sorted(set(a) & set(b))
    wins = losses = ties = 0
    for key in keys:
        av = bool(a[key].get("success"))
        bv = bool(b[key].get("success"))
        if av and not bv:
            wins += 1
        elif bv and not av:
            losses += 1
        else:
            ties += 1
    a_success = sum(bool(a[key].get("success")) for key in keys)
    b_success = sum(bool(b[key].get("success")) for key in keys)
    a_cat = sum(bool(a[key].get("catastrophic")) for key in keys)
    b_cat = sum(bool(b[key].get("catastrophic")) for key in keys)
    n = len(keys)
    return {
        "arm_id": a_id,
        "comparison_arm_id": b_id,
        "matched_cases": n,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "net_wins": wins - losses,
        "successes": a_success,
        "comparison_successes": b_success,
        "success_rate": a_success / n if n else 0.0,
        "comparison_success_rate": b_success / n if n else 0.0,
        "success_rate_delta": (a_success - b_success) / n if n else 0.0,
        "catastrophes": a_cat,
        "comparison_catastrophes": b_cat,
        "catastrophes_added": a_cat - b_cat,
    }


def _protocol_failures(runtime: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    trials = [dict(row) for row in runtime.get("trials") or []]
    calls = [dict(row) for row in runtime.get("model_calls") or []]
    action_budget = dict(runtime.get("action_budget") or {})
    by_kind = dict(action_budget.get("by_kind") or {})
    combined_used = int(action_budget.get("combined_used") or 0)
    combined_limit = int(action_budget.get("limit") or 0)
    if runtime.get("protocol_revision") != S2_PROTOCOL_REVISION:
        failures.append("protocol_revision_s2_r1")
    if runtime.get("holdout") != S2_HOLDOUT:
        failures.append("holdout_b_r1")
    if int(runtime.get("physical_model_calls") or 0) != S2_EXACT_BUDGET:
        failures.append("exact_720_calls")
    if int(runtime.get("inference_action_delta") or 0) != S2_EXACT_BUDGET:
        failures.append("exact_720_inference_actions")
    if combined_limit != S2_COMBINED_ACTION_BUDGET:
        failures.append("combined_action_budget_limit_732")
    if combined_used > S2_COMBINED_ACTION_BUDGET or combined_used < S2_EXACT_BUDGET:
        failures.append("combined_action_usage_within_declared_budget")
    if int(by_kind.get("model_call") or 0) != S2_EXACT_BUDGET:
        failures.append("combined_budget_records_720_model_calls")
    unknown = set(by_kind) - {"model_call", "provenance_api_call"}
    if unknown:
        failures.append("unexpected_external_action_classes")
    if len(trials) != S2_TRIAL_COUNT:
        failures.append("exact_360_trials")
    if len(calls) != S2_EXACT_BUDGET:
        failures.append("exact_720_model_call_rows")
    if any(bool(row.get("cache_hit")) for row in calls):
        failures.append("zero_cache_hits")
    if any(row.get("complete") is not True or int(row.get("calls_used") or 0) != 2 for row in trials):
        failures.append("two_calls_per_trial_complete")
    trial_counts = Counter(str(row.get("arm_id")) for row in trials)
    call_counts = Counter(str(row.get("arm_id")) for row in calls)
    if trial_counts != Counter({arm: S2_MATCHED_CASES for arm in REAL_ARM_IDS}):
        failures.append("72_trials_per_arm")
    if call_counts != Counter({arm: S2_PER_ARM_CALL_CAP for arm in REAL_ARM_IDS}):
        failures.append("144_calls_per_arm")
    return failures


def _stratum_support(trials: list[dict[str, Any]], dimension: str) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    support: list[str] = []
    values = sorted({row.get(dimension) for row in trials}, key=str)
    for value in values:
        a = [row for row in trials if row.get(dimension) == value and row.get("arm_id") == "S2-B3"]
        b = [row for row in trials if row.get(dimension) == value and row.get("arm_id") == "S2-B0"]
        effect = _pair(a, b, a_id="S2-B3", b_id="S2-B0")
        effect[dimension] = value
        out.append(effect)
        if effect["net_wins"] >= 2 and effect["catastrophes_added"] <= 0:
            support.append(f"{dimension}:{value}")
    return out, support


def summarize_s2(runtime: dict[str, Any]) -> dict[str, Any]:
    trials = [dict(row) for row in runtime.get("trials") or []]
    failures = _protocol_failures(runtime)
    by_arm = {arm: [row for row in trials if row.get("arm_id") == arm] for arm in REAL_ARM_IDS}

    arm_summaries = _summary_rows(trials, ("arm_id",))
    family_summaries = _summary_rows(trials, ("arm_id", "family"))
    perturbation_summaries = _summary_rows(trials, ("arm_id", "perturbation_class"))
    complexity_summaries = _summary_rows(trials, ("arm_id", "complexity"))

    pairs: list[dict[str, Any]] = []
    for arm in REAL_ARM_IDS:
        if arm != "S2-B0":
            pairs.append(_pair(by_arm[arm], by_arm["S2-B0"], a_id=arm, b_id="S2-B0"))
    pairs.append(_pair(by_arm["S2-B3"], by_arm["S2-B4"], a_id="S2-B3", b_id="S2-B4"))
    pairs.append(_pair(by_arm["S2-B2"], by_arm["S2-B1"], a_id="S2-B2", b_id="S2-B1"))
    pair_index = {f"{row['arm_id']}|{row['comparison_arm_id']}": row for row in pairs}

    all_task_ids = sorted({str(row.get("task_id")) for row in trials})
    successes_by_task = {
        task_id: any(bool(row.get("success")) for row in trials if str(row.get("task_id")) == task_id)
        for task_id in all_task_ids
    }
    oracle_successes = sum(successes_by_task.values())
    observed_oracle = {
        "matched_cases": len(all_task_ids),
        "successes": oracle_successes,
        "success_rate": oracle_successes / len(all_task_ids) if all_task_ids else 0.0,
        "source": "observed_real_arm_outcomes_only",
        "new_inference_calls": 0,
    }
    regret_rows: list[dict[str, Any]] = []
    regret_index: dict[str, float] = {}
    for arm in REAL_ARM_IDS:
        arm_success = sum(bool(row.get("success")) for row in by_arm[arm])
        regret = (oracle_successes - arm_success) / len(all_task_ids) if all_task_ids else 0.0
        regret_index[arm] = regret
        regret_rows.append({
            "arm_id": arm,
            "oracle_successes": oracle_successes,
            "arm_successes": arm_success,
            "matched_cases": len(all_task_ids),
            "regret_to_oracle": regret,
        })

    transition_counts: Counter[tuple[str, str, str]] = Counter()
    for row in trials:
        actions = list(row.get("actions_selected") or [])
        if len(actions) == 2:
            transition_counts[(str(row.get("arm_id")), str(actions[0]), str(actions[1]))] += 1
    transition_matrix = [
        {"arm_id": arm, "first_action": first, "second_action": second, "count": count}
        for (arm, first, second), count in sorted(transition_counts.items())
    ]

    family_effects, family_support = _stratum_support(trials, "family")
    perturb_effects, perturb_support = _stratum_support(trials, "perturbation_class")
    supported = family_support + perturb_support

    divergence_task_ids: set[str] = set()
    for item in runtime.get("stochastic_divergence") or []:
        if item.get("outcome_changed"):
            divergence_task_ids.update(str(value) for value in (item.get("task_ids") or []) if value)
    clean = [row for row in trials if str(row.get("task_id")) not in divergence_task_ids]
    clean_by_arm = {arm: [row for row in clean if row.get("arm_id") == arm] for arm in REAL_ARM_IDS}
    divergence_b0 = _pair(clean_by_arm["S2-B3"], clean_by_arm["S2-B0"], a_id="S2-B3", b_id="S2-B0")
    divergence_b4 = _pair(clean_by_arm["S2-B3"], clean_by_arm["S2-B4"], a_id="S2-B3", b_id="S2-B4")

    transitions = [{
        "arm_id": row.get("arm_id"),
        "task_id": row.get("task_id"),
        "initial_success": bool(row.get("initial_success")),
        "final_success": bool(row.get("success")),
        "initial_catastrophic": bool(row.get("initial_catastrophic")),
        "final_catastrophic": bool(row.get("catastrophic")),
        "classification": (
            "FAIL_TO_SUCCESS" if not row.get("initial_success") and row.get("success")
            else "FAIL_TO_FAIL"
        ),
    } for row in trials]

    return {
        "protocol_revision": S2_PROTOCOL_REVISION,
        "holdout": S2_HOLDOUT,
        "protocol_valid_for_primary_claim": not failures,
        "protocol_failures": failures,
        "matched_case_count": len(all_task_ids),
        "arm_summaries": arm_summaries,
        "family_summaries": family_summaries,
        "perturbation_summaries": perturbation_summaries,
        "complexity_summaries": complexity_summaries,
        "pairwise_effects": pairs,
        "pairwise_index": pair_index,
        "observed_oracle": observed_oracle,
        "regret_to_oracle": regret_rows,
        "regret_index": regret_index,
        "action_transition_matrix": transition_matrix,
        "family_effects_b3_vs_b0": family_effects,
        "fault_mode_effects": perturb_effects,
        "supported_strata_b3_vs_b0": supported,
        "stochastic_divergence": list(runtime.get("stochastic_divergence") or []),
        "divergence_affected_task_ids": sorted(divergence_task_ids),
        "divergence_excluded_b3_vs_b0": divergence_b0,
        "divergence_excluded_b3_vs_b4": divergence_b4,
        "transitions": transitions,
    }


def derive_s2_verdict(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("protocol_valid_for_primary_claim") is not True:
        failures = list(summary.get("protocol_failures") or [])
        return {
            "verdict": "S2_INVALID_PROTOCOL",
            "reason": "S2-R1 primary claim withheld because protocol/integrity gates failed: " + ", ".join(failures),
            "winning_arm_id": None,
            "tier_a_architecture_claim": False,
            "protocol_valid_for_primary_claim": False,
            "protocol_failures": failures,
            "protocol_revision": S2_PROTOCOL_REVISION,
            "holdout": S2_HOLDOUT,
        }

    pairs = dict(summary.get("pairwise_index") or {})
    b0 = dict(pairs.get("S2-B3|S2-B0") or {})
    b4 = dict(pairs.get("S2-B3|S2-B4") or {})
    b2b1 = dict(pairs.get("S2-B2|S2-B1") or {})
    clean_b0 = dict(summary.get("divergence_excluded_b3_vs_b0") or {})
    clean_b4 = dict(summary.get("divergence_excluded_b3_vs_b4") or {})
    supported = list(summary.get("supported_strata_b3_vs_b0") or [])
    regrets = dict(summary.get("regret_index") or {})

    incremental = int(b2b1.get("net_wins") or 0) >= 3 and int(b2b1.get("catastrophes_added") or 0) <= 0
    survives_divergence = (
        int(clean_b0.get("net_wins") or 0) >= 4
        and float(clean_b0.get("success_rate_delta") or 0.0) >= 0.05
        and int(clean_b0.get("catastrophes_added") or 0) <= 0
        and int(clean_b4.get("net_wins") or 0) >= 4
        and int(clean_b4.get("catastrophes_added") or 0) <= 0
    )
    signal = (
        int(b0.get("net_wins") or 0) >= 4
        and int(b4.get("net_wins") or 0) >= 4
        and float(b0.get("success_rate_delta") or 0.0) >= 0.05
        and int(b0.get("catastrophes_added") or 0) <= 0
        and len(supported) >= 3
        and float(regrets.get("S2-B3", 1.0)) < float(regrets.get("S2-B0", 1.0))
        and survives_divergence
    )
    harmful = (
        int(b0.get("net_wins") or 0) <= -4
        or (int(b0.get("catastrophes_added") or 0) >= 2 and int(b0.get("net_wins") or 0) <= 0)
    )

    if signal:
        verdict = "S2_ADAPTIVE_ROUTING_SIGNAL"
        reason = "Rich verified evidence-state routing beat fixed and random controls, improved oracle regret without added catastrophes, generalized across strata, and survived stochastic-divergence exclusion."
        winner = "S2-B3"
        architecture = True
    elif harmful:
        verdict = "S2_ADAPTIVE_ROUTING_HARMFUL"
        reason = "Rich evidence-state routing met the preregistered harmful boundary against the fixed control."
        winner = None
        architecture = True
    else:
        verdict = "S2_SCREEN_NON_DECISIVE"
        reason = "S2-R1 completed validly but the frozen adaptive-routing promotion/harm thresholds were not met."
        winner = None
        architecture = False

    return {
        "verdict": verdict,
        "reason": reason,
        "winning_arm_id": winner,
        "tier_a_architecture_claim": architecture,
        "protocol_valid_for_primary_claim": True,
        "protocol_failures": [],
        "protocol_revision": S2_PROTOCOL_REVISION,
        "holdout": S2_HOLDOUT,
        "matched_case_count": int(summary.get("matched_case_count") or 0),
        "failure_evidence_incremental_signal": incremental,
        "stochastic_divergence_exclusion_survives": survives_divergence,
    }
