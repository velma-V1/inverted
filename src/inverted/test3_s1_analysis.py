from __future__ import annotations

from collections import defaultdict
import statistics
from typing import Any, Iterable


S1_R1_PROTOCOL = "S1-R1"
S1_R1_HOLDOUT = "A-R1"
S1_R1_MATCHED_TASKS = 10
S1_R1_CALLS_PER_ARM_TASK = 2
S1_R1_CALLS_PER_ARM = 20
S1_R1_TOTAL_CALLS = 80


def _complete_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if row.get("complete") is True and row.get("task_id") and row.get("arm_id")]


def _matched_task_ids(rows: list[dict[str, Any]]) -> list[str]:
    arm_ids = sorted({str(row["arm_id"]) for row in rows})
    by_task: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_task[str(row["task_id"])].add(str(row["arm_id"]))
    required = set(arm_ids)
    return sorted(task_id for task_id, observed in by_task.items() if observed == required)


def _mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values: list[float] = []
    for row in rows:
        value = row.get(field)
        if value not in (None, ""):
            values.append(float(value))
    return statistics.fmean(values) if values else None


def _pairwise(
    rows_by_key: dict[tuple[str, str], dict[str, Any]],
    task_ids: list[str],
    arm_id: str,
    reference_arm_id: str,
) -> dict[str, Any]:
    wins_created = wins_destroyed = catastrophes_added = catastrophes_removed = 0
    arm_rows: list[dict[str, Any]] = []
    ref_rows: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for task_id in task_ids:
        arm = rows_by_key[(task_id, arm_id)]
        ref = rows_by_key[(task_id, reference_arm_id)]
        arm_rows.append(arm)
        ref_rows.append(ref)
        a = bool(arm.get("success")); b = bool(ref.get("success"))
        ac = bool(arm.get("catastrophic")); bc = bool(ref.get("catastrophic"))
        wins_created += int(a and not b)
        wins_destroyed += int(b and not a)
        catastrophes_added += int(ac and not bc)
        catastrophes_removed += int(bc and not ac)
        transitions.append({
            "task_id": task_id,
            "arm_id": arm_id,
            "reference_arm_id": reference_arm_id,
            "reference_success": b,
            "arm_success": a,
            "reference_catastrophic": bc,
            "arm_catastrophic": ac,
            "transition": (
                "FAIL_TO_SUCCESS" if a and not b else
                "SUCCESS_TO_FAIL" if b and not a else
                "SUCCESS_TO_SUCCESS" if a and b else "FAIL_TO_FAIL"
            ),
        })
    n = len(task_ids)
    arm_successes = sum(bool(row.get("success")) for row in arm_rows)
    ref_successes = sum(bool(row.get("success")) for row in ref_rows)
    return {
        "arm_id": arm_id,
        "reference_arm_id": reference_arm_id,
        "matched_tasks": n,
        "arm_successes": arm_successes,
        "reference_successes": ref_successes,
        "arm_success_rate": arm_successes / n if n else None,
        "reference_success_rate": ref_successes / n if n else None,
        "effect_pp": ((arm_successes - ref_successes) / n * 100.0) if n else None,
        "wins_created": wins_created,
        "wins_destroyed": wins_destroyed,
        "net_wins": wins_created - wins_destroyed,
        "catastrophes_added": catastrophes_added,
        "catastrophes_removed": catastrophes_removed,
        "mean_physical_calls": _mean(arm_rows, "physical_calls_added"),
        "reference_mean_physical_calls": _mean(ref_rows, "physical_calls_added"),
        "mean_total_tokens": _mean(arm_rows, "total_tokens"),
        "reference_mean_total_tokens": _mean(ref_rows, "total_tokens"),
        "mean_active_inference_calls": _mean(arm_rows, "active_inference_calls"),
        "mean_shadow_inference_calls": _mean(arm_rows, "shadow_inference_calls"),
        "transitions": transitions,
    }


def _protocol_gate(matched: list[dict[str, Any]], arm_ids: list[str], matched_ids: list[str]) -> tuple[bool, list[str], dict[str, Any]]:
    failures: list[str] = []
    revisions = {str(row.get("protocol_revision") or "") for row in matched}
    holdouts = {str(row.get("holdout") or "") for row in matched}
    total_calls = sum(int(row.get("physical_calls_added") or 0) for row in matched)
    calls_by_arm = {
        arm_id: sum(int(row.get("physical_calls_added") or 0) for row in matched if str(row.get("arm_id")) == arm_id)
        for arm_id in arm_ids
    }
    all_two_calls = bool(matched) and all(int(row.get("physical_calls_added") or 0) == S1_R1_CALLS_PER_ARM_TASK for row in matched)
    all_seed_failures = bool(matched) and all(row.get("seed_failure_verified") is True for row in matched)
    all_active = bool(matched) and all(int(row.get("active_inference_calls") or 0) >= 1 for row in matched)
    all_call_partition = bool(matched) and all(
        int(row.get("active_inference_calls") or 0) + int(row.get("shadow_inference_calls") or 0) == S1_R1_CALLS_PER_ARM_TASK
        for row in matched
    )
    cache_hits = sum(int(row.get("cache_hits") or 0) for row in matched)
    fixed_first = {
        str(row.get("first_active_component") or "")
        for row in matched
        if str(row.get("arm_id") or "") in {"S1-A1", "S1-A2", "S1-A3"}
    }
    fixed_first.discard("")

    if revisions != {S1_R1_PROTOCOL}:
        failures.append("protocol_revision_s1_r1")
    if holdouts != {S1_R1_HOLDOUT}:
        failures.append("holdout_a_r1")
    if len(arm_ids) != 4 or arm_ids != ["S1-A0", "S1-A1", "S1-A2", "S1-A3"]:
        failures.append("frozen_four_arms")
    if len(matched_ids) != S1_R1_MATCHED_TASKS:
        failures.append("exactly_10_matched_tasks")
    if not all_two_calls or not all_call_partition:
        failures.append("exactly_2_calls_per_arm_task")
    if any(calls_by_arm.get(arm_id) != S1_R1_CALLS_PER_ARM for arm_id in arm_ids):
        failures.append("exactly_20_calls_per_arm")
    if total_calls != S1_R1_TOTAL_CALLS:
        failures.append("exactly_80_physical_calls")
    if not all_seed_failures:
        failures.append("all_seed_failures_verified")
    if not all_active:
        failures.append("all_arm_tasks_have_active_intervention")
    if len(fixed_first) < 2:
        failures.append("distinct_fixed_first_active_components")
    if cache_hits != 0:
        failures.append("zero_cache_hits")

    exposure = {
        "all_seed_failures_verified": all_seed_failures,
        "all_arm_tasks_have_active_intervention": all_active,
        "all_calls_partitioned_active_or_shadow": all_call_partition,
        "distinct_fixed_first_active_components": len(fixed_first),
        "fixed_first_active_components": sorted(fixed_first),
        "cache_hits": cache_hits,
    }
    return not failures, failures, exposure


def summarize_s1(
    rows: Iterable[dict[str, Any]],
    *,
    baseline_arm: str = "S1-A0",
    random_control_arm: str = "S1-A3",
) -> dict[str, Any]:
    all_rows = [dict(row) for row in rows]
    complete = _complete_rows(all_rows)
    arm_ids = sorted({str(row["arm_id"]) for row in complete})
    if baseline_arm not in arm_ids or random_control_arm not in arm_ids:
        raise ValueError("S1 analysis is missing frozen baseline or random-control arm")
    matched_ids = _matched_task_ids(complete)
    matched_set = set(matched_ids)
    matched = [row for row in complete if str(row["task_id"]) in matched_set]
    by_key = {(str(row["task_id"]), str(row["arm_id"])): row for row in matched}

    arm_summaries: list[dict[str, Any]] = []
    for arm_id in arm_ids:
        group = [row for row in matched if str(row["arm_id"]) == arm_id]
        n = len(group)
        successes = sum(bool(row.get("success")) for row in group)
        catastrophes = sum(bool(row.get("catastrophic")) for row in group)
        physical_calls = sum(int(row.get("physical_calls_added") or 0) for row in group)
        active_calls = sum(int(row.get("active_inference_calls") or 0) for row in group)
        shadow_calls = sum(int(row.get("shadow_inference_calls") or 0) for row in group)
        tokens = sum(int(row.get("total_tokens") or 0) for row in group)
        arm_summaries.append({
            "arm_id": arm_id,
            "matched_tasks": n,
            "successes": successes,
            "matched_success_rate": successes / n if n else None,
            "catastrophes": catastrophes,
            "catastrophe_rate": catastrophes / n if n else None,
            "physical_calls": physical_calls,
            "active_inference_calls": active_calls,
            "shadow_inference_calls": shadow_calls,
            "mean_physical_calls": physical_calls / n if n else None,
            "mean_active_inference_calls": active_calls / n if n else None,
            "mean_shadow_inference_calls": shadow_calls / n if n else None,
            "total_tokens": tokens,
            "mean_total_tokens": tokens / n if n else None,
            "successes_per_physical_call": successes / physical_calls if physical_calls else None,
            "first_active_components": sorted({str(row.get("first_active_component") or "") for row in group if row.get("first_active_component")}),
        })

    effects: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    references = [baseline_arm, random_control_arm]
    for arm_id in arm_ids:
        for reference in references:
            if arm_id == reference:
                continue
            effect = _pairwise(by_key, matched_ids, arm_id, reference)
            transitions.extend(effect.pop("transitions"))
            effects.append(effect)

    protocol_valid, protocol_failures, exposure = _protocol_gate(matched, arm_ids, matched_ids)
    return {
        "baseline_arm_id": baseline_arm,
        "random_control_arm_id": random_control_arm,
        "arm_ids": arm_ids,
        "matched_task_ids": matched_ids,
        "matched_task_count": len(matched_ids),
        "total_matched_physical_calls": sum(int(row.get("physical_calls_added") or 0) for row in matched),
        "protocol_revision": S1_R1_PROTOCOL if protocol_valid else None,
        "holdout": S1_R1_HOLDOUT if protocol_valid else None,
        "protocol_valid_for_primary_claim": protocol_valid,
        "protocol_failures": protocol_failures,
        "intervention_exposure": exposure,
        "arm_summaries": arm_summaries,
        "pairwise_effects": effects,
        "transitions": transitions,
        "incomplete_or_unmatched_rows": len(all_rows) - len(matched),
    }


def _effect(summary: dict[str, Any], arm_id: str, reference: str) -> dict[str, Any] | None:
    return next((
        row for row in summary.get("pairwise_effects", [])
        if row.get("arm_id") == arm_id and row.get("reference_arm_id") == reference
    ), None)


def derive_s1_verdict(summary: dict[str, Any], *, full_power_clusters: int | None) -> dict[str, Any]:
    matched = int(summary.get("matched_task_count") or 0)
    underpowered = bool(full_power_clusters is not None and matched < int(full_power_clusters))
    if summary.get("protocol_valid_for_primary_claim") is not True:
        failures = list(summary.get("protocol_failures") or [])
        return {
            "verdict": "S1_INVALID_INTERVENTION_EXPOSURE",
            "reason": "S1 primary causal claim withheld because the corrective protocol gate failed: " + ", ".join(failures),
            "winning_arm_id": None,
            "matched_task_count": matched,
            "tier_a_architecture_claim": False,
            "protocol_valid_for_primary_claim": False,
            "protocol_failures": failures,
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": True,
        }

    baseline = str(summary.get("baseline_arm_id") or "S1-A0")
    random_control = str(summary.get("random_control_arm_id") or "S1-A3")
    fixed_arms = [arm for arm in summary.get("arm_ids", []) if arm not in {baseline, random_control}]
    strong: list[tuple[int, int, str, dict[str, Any], dict[str, Any]]] = []
    for arm_id in fixed_arms:
        vs_base = _effect(summary, arm_id, baseline)
        vs_random = _effect(summary, arm_id, random_control)
        if not vs_base or not vs_random:
            continue
        if (
            int(vs_base.get("net_wins") or 0) >= 2
            and int(vs_base.get("catastrophes_added") or 0) == 0
            and int(vs_random.get("net_wins") or 0) >= 1
        ):
            strong.append((
                int(vs_base["net_wins"]),
                int(vs_random["net_wins"]),
                str(arm_id),
                vs_base,
                vs_random,
            ))
    strong.sort(key=lambda item: (-item[0], -item[1], item[2]))

    if strong:
        _, _, winner, vs_base, vs_random = strong[0]
        return {
            "verdict": "S1_STRONG_FIXED_ORDER_SIGNAL",
            "reason": (
                f"{winner} produced at least two matched net wins over the best-single baseline, "
                "added no catastrophes, and also beat the random-order control on matched Holdout A-R1 tasks."
            ),
            "winning_arm_id": winner,
            "matched_task_count": matched,
            "net_wins_vs_baseline": vs_base["net_wins"],
            "net_wins_vs_random_control": vs_random["net_wins"],
            "catastrophes_added_vs_baseline": vs_base["catastrophes_added"],
            "tier_a_architecture_claim": True,
            "protocol_valid_for_primary_claim": True,
            "claim_scope": "large fixed-order signal on corrective S1-R1 Holdout A-R1; not proof of small-effect magnitude",
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": underpowered,
        }

    return {
        "verdict": "S1_SCREEN_NON_DECISIVE",
        "reason": (
            "No production fixed order crossed the preregistered large-signal screen under the valid S1-R1 exposure contract. "
            "Because S1 is intentionally bounded, this does not prove that small fixed-order effects are absent."
        ),
        "winning_arm_id": None,
        "matched_task_count": matched,
        "tier_a_architecture_claim": False,
        "protocol_valid_for_primary_claim": True,
        "full_power_cluster_requirement": full_power_clusters,
        "cannot_rule_out_target_effect": underpowered,
        "next_section_implication": "sharply reduce universal fixed-order search and proceed to adaptive-routing S2 unless a large S1 signal appears",
    }
