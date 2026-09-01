from __future__ import annotations

from collections import defaultdict
import statistics
from typing import Any, Iterable


S1_R1_PROTOCOL = "S1-R1"
S1_R1_HOLDOUT = "A-R1"
S1_R2_PROTOCOL = "S1-R2"
S1_R2_HOLDOUT = "A-R2"
S1_CALLS_PER_ARM_TASK = 2

_PROTOCOLS = {
    S1_R1_PROTOCOL: {
        "protocol": S1_R1_PROTOCOL,
        "holdout": S1_R1_HOLDOUT,
        "matched_tasks": 10,
        "calls_per_arm": 20,
        "total_calls": 80,
        "matched_failure": "exactly_10_matched_tasks",
        "arm_calls_failure": "exactly_20_calls_per_arm",
        "total_calls_failure": "exactly_80_physical_calls",
    },
    S1_R2_PROTOCOL: {
        "protocol": S1_R2_PROTOCOL,
        "holdout": S1_R2_HOLDOUT,
        "matched_tasks": 25,
        "calls_per_arm": 50,
        "total_calls": 200,
        "matched_failure": "exactly_25_matched_tasks",
        "arm_calls_failure": "exactly_50_calls_per_arm",
        "total_calls_failure": "exactly_200_physical_calls",
    },
}


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


def _select_contract(matched: list[dict[str, Any]]) -> dict[str, Any]:
    revisions = {str(row.get("protocol_revision") or "") for row in matched}
    if revisions == {S1_R2_PROTOCOL}:
        return _PROTOCOLS[S1_R2_PROTOCOL]
    # Preserve legacy/R1 invalid-run diagnostics with the original 80-call labels.
    return _PROTOCOLS[S1_R1_PROTOCOL]


def _protocol_gate(
    matched: list[dict[str, Any]],
    arm_ids: list[str],
    matched_ids: list[str],
    contract: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    failures: list[str] = []
    revisions = {str(row.get("protocol_revision") or "") for row in matched}
    holdouts = {str(row.get("holdout") or "") for row in matched}
    total_calls = sum(int(row.get("physical_calls_added") or 0) for row in matched)
    calls_by_arm = {
        arm_id: sum(int(row.get("physical_calls_added") or 0) for row in matched if str(row.get("arm_id")) == arm_id)
        for arm_id in arm_ids
    }
    all_two_calls = bool(matched) and all(int(row.get("physical_calls_added") or 0) == S1_CALLS_PER_ARM_TASK for row in matched)
    all_seed_failures = bool(matched) and all(row.get("seed_failure_verified") is True for row in matched)
    all_active = bool(matched) and all(int(row.get("active_inference_calls") or 0) >= 1 for row in matched)
    all_call_partition = bool(matched) and all(
        int(row.get("active_inference_calls") or 0) + int(row.get("shadow_inference_calls") or 0) == S1_CALLS_PER_ARM_TASK
        for row in matched
    )
    cache_hits = sum(int(row.get("cache_hits") or 0) for row in matched)
    fixed_first = {
        str(row.get("first_active_component") or "")
        for row in matched
        if str(row.get("arm_id") or "") in {"S1-A1", "S1-A2", "S1-A3"}
    }
    fixed_first.discard("")

    expected_protocol = str(contract["protocol"])
    expected_holdout = str(contract["holdout"])
    if revisions != {expected_protocol}:
        failures.append("protocol_revision_" + expected_protocol.lower().replace("-", "_"))
    if holdouts != {expected_holdout}:
        failures.append("holdout_" + expected_holdout.lower().replace("-", "_"))
    if arm_ids != ["S1-A0", "S1-A1", "S1-A2", "S1-A3"]:
        failures.append("frozen_four_arms")
    if len(matched_ids) != int(contract["matched_tasks"]):
        failures.append(str(contract["matched_failure"]))
    if not all_two_calls or not all_call_partition:
        failures.append("exactly_2_calls_per_arm_task")
    if any(calls_by_arm.get(arm_id) != int(contract["calls_per_arm"]) for arm_id in arm_ids):
        failures.append(str(contract["arm_calls_failure"]))
    if total_calls != int(contract["total_calls"]):
        failures.append(str(contract["total_calls_failure"]))
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


def _requirement_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    repaired = regressed = new_failures = preservation = ordering = missing_actions = 0
    containment_clean = 0
    for row in rows:
        seed_passed = set(row.get("seed_passed_requirements") or [])
        seed_failed = set(row.get("seed_failed_requirements") or [])
        final_failed = set(row.get("final_failed_requirements") or [])
        kinds = dict(row.get("requirement_kinds") or {})
        repaired_ids = seed_failed - final_failed
        regressed_ids = seed_passed & final_failed
        new_ids = final_failed - seed_failed
        repaired += len(repaired_ids)
        regressed += len(regressed_ids)
        new_failures += len(new_ids)
        preservation += sum(kinds.get(req_id) == "preserve" for req_id in final_failed)
        ordering += sum(kinds.get(req_id) == "action_before" for req_id in final_failed)
        missing_actions += sum(kinds.get(req_id) == "action_present" for req_id in final_failed)
        containment_clean += int(bool(repaired_ids) and not regressed_ids and not final_failed)
    return {
        "requirements_repaired": repaired,
        "requirements_regressed": regressed,
        "new_failures_introduced": new_failures,
        "preservation_violations": preservation,
        "action_order_violations": ordering,
        "missing_required_actions": missing_actions,
        "clean_containment_recoveries": containment_clean,
    }


def _arm_summary(arm_id: str, group: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(group)
    successes = sum(bool(row.get("success")) for row in group)
    catastrophes = sum(bool(row.get("catastrophic")) for row in group)
    physical_calls = sum(int(row.get("physical_calls_added") or 0) for row in group)
    active_calls = sum(int(row.get("active_inference_calls") or 0) for row in group)
    shadow_calls = sum(int(row.get("shadow_inference_calls") or 0) for row in group)
    tokens = sum(int(row.get("total_tokens") or 0) for row in group)
    return {
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
        **_requirement_metrics(group),
    }


def _family_summaries(
    matched: list[dict[str, Any]],
    arm_ids: list[str],
    baseline_arm: str,
    random_control_arm: str,
) -> list[dict[str, Any]]:
    families = sorted({str(row.get("family") or "") for row in matched if row.get("family")})
    output: list[dict[str, Any]] = []
    for family in families:
        family_rows = [row for row in matched if str(row.get("family") or "") == family]
        task_ids = sorted({str(row["task_id"]) for row in family_rows})
        by_key = {(str(row["task_id"]), str(row["arm_id"])): row for row in family_rows}
        arm_summaries = [
            _arm_summary(arm_id, [row for row in family_rows if str(row["arm_id"]) == arm_id])
            for arm_id in arm_ids
        ]
        effects: list[dict[str, Any]] = []
        for arm_id in arm_ids:
            for reference in (baseline_arm, random_control_arm):
                if arm_id == reference:
                    continue
                effect = _pairwise(by_key, task_ids, arm_id, reference)
                effect.pop("transitions")
                effect["family"] = family
                effects.append(effect)
        output.append({
            "family": family,
            "task_count": len(task_ids),
            "arm_summaries": arm_summaries,
            "pairwise_effects": effects,
        })
    return output


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

    arm_summaries = [
        _arm_summary(arm_id, [row for row in matched if str(row["arm_id"]) == arm_id])
        for arm_id in arm_ids
    ]

    effects: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for arm_id in arm_ids:
        for reference in (baseline_arm, random_control_arm):
            if arm_id == reference:
                continue
            effect = _pairwise(by_key, matched_ids, arm_id, reference)
            transitions.extend(effect.pop("transitions"))
            effects.append(effect)

    contract = _select_contract(matched)
    protocol_valid, protocol_failures, exposure = _protocol_gate(matched, arm_ids, matched_ids, contract)
    families = _family_summaries(matched, arm_ids, baseline_arm, random_control_arm)
    return {
        "baseline_arm_id": baseline_arm,
        "random_control_arm_id": random_control_arm,
        "arm_ids": arm_ids,
        "matched_task_ids": matched_ids,
        "matched_task_count": len(matched_ids),
        "total_matched_physical_calls": sum(int(row.get("physical_calls_added") or 0) for row in matched),
        "protocol_revision": contract["protocol"] if protocol_valid else None,
        "holdout": contract["holdout"] if protocol_valid else None,
        "detected_protocol_contract": contract["protocol"],
        "protocol_valid_for_primary_claim": protocol_valid,
        "protocol_failures": protocol_failures,
        "intervention_exposure": exposure,
        "arm_summaries": arm_summaries,
        "pairwise_effects": effects,
        "family_summaries": families,
        "transitions": transitions,
        "incomplete_or_unmatched_rows": len(all_rows) - len(matched),
    }


def _effect(summary: dict[str, Any], arm_id: str, reference: str) -> dict[str, Any] | None:
    return next((
        row for row in summary.get("pairwise_effects", [])
        if row.get("arm_id") == arm_id and row.get("reference_arm_id") == reference
    ), None)


def _family_effect(summary: dict[str, Any], family: str, arm_id: str, reference: str) -> dict[str, Any] | None:
    family_row = next((row for row in summary.get("family_summaries", []) if row.get("family") == family), None)
    if not family_row:
        return None
    return next((
        row for row in family_row.get("pairwise_effects", [])
        if row.get("arm_id") == arm_id and row.get("reference_arm_id") == reference
    ), None)


def _invalid_verdict(summary: dict[str, Any], full_power_clusters: int | None) -> dict[str, Any]:
    matched = int(summary.get("matched_task_count") or 0)
    failures = list(summary.get("protocol_failures") or [])
    is_r2 = summary.get("detected_protocol_contract") == S1_R2_PROTOCOL
    return {
        "verdict": "S1_R2_INVALID_PROTOCOL" if is_r2 else "S1_INVALID_INTERVENTION_EXPOSURE",
        "reason": "S1 primary causal claim withheld because the protocol gate failed: " + ", ".join(failures),
        "winning_arm_id": None,
        "matched_task_count": matched,
        "tier_a_architecture_claim": False,
        "protocol_valid_for_primary_claim": False,
        "protocol_failures": failures,
        "full_power_cluster_requirement": full_power_clusters,
        "cannot_rule_out_target_effect": True,
    }


def _derive_r1(summary: dict[str, Any], *, full_power_clusters: int | None, underpowered: bool) -> dict[str, Any]:
    matched = int(summary.get("matched_task_count") or 0)
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
            strong.append((int(vs_base["net_wins"]), int(vs_random["net_wins"]), str(arm_id), vs_base, vs_random))
    strong.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if strong:
        _, _, winner, vs_base, vs_random = strong[0]
        return {
            "verdict": "S1_STRONG_FIXED_ORDER_SIGNAL",
            "reason": f"{winner} crossed the preregistered S1-R1 large-signal screen.",
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
        "reason": "No production fixed order crossed the preregistered large-signal screen under the valid S1-R1 exposure contract.",
        "winning_arm_id": None,
        "matched_task_count": matched,
        "tier_a_architecture_claim": False,
        "protocol_valid_for_primary_claim": True,
        "full_power_cluster_requirement": full_power_clusters,
        "cannot_rule_out_target_effect": underpowered,
        "next_section_implication": "sharply reduce universal fixed-order search and proceed to adaptive-routing S2 unless later evidence changes the preregistration",
    }


def _derive_r2(summary: dict[str, Any], *, full_power_clusters: int | None, underpowered: bool) -> dict[str, Any]:
    matched = int(summary.get("matched_task_count") or 0)
    baseline = str(summary.get("baseline_arm_id") or "S1-A0")
    random_control = str(summary.get("random_control_arm_id") or "S1-A3")
    fixed_arms = [arm for arm in summary.get("arm_ids", []) if arm in {"S1-A1", "S1-A2"}]

    aggregate: list[tuple[int, int, str, dict[str, Any], dict[str, Any]]] = []
    for arm_id in fixed_arms:
        vs_base = _effect(summary, arm_id, baseline)
        vs_random = _effect(summary, arm_id, random_control)
        if not vs_base or not vs_random:
            continue
        if (
            int(vs_base.get("net_wins") or 0) >= 5
            and int(vs_random.get("net_wins") or 0) >= 3
            and int(vs_base.get("catastrophes_added") or 0) == 0
        ):
            aggregate.append((int(vs_base["net_wins"]), int(vs_random["net_wins"]), arm_id, vs_base, vs_random))
    aggregate.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if aggregate:
        _, _, winner, vs_base, vs_random = aggregate[0]
        return {
            "verdict": "S1_R2_FIXED_ORDER_LARGE_SIGNAL",
            "reason": f"{winner} crossed the preregistered 25-task S1-R2 aggregate large-signal threshold.",
            "winning_arm_id": winner,
            "matched_task_count": matched,
            "net_wins_vs_baseline": vs_base["net_wins"],
            "net_wins_vs_random_control": vs_random["net_wins"],
            "catastrophes_added_vs_baseline": vs_base["catastrophes_added"],
            "tier_a_architecture_claim": True,
            "protocol_valid_for_primary_claim": True,
            "claim_scope": "large fixed-order signal across six-family S1-R2 Holdout A-R2; not proof of small-effect magnitude",
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": underpowered,
        }

    conditional: list[tuple[int, int, str, list[str]]] = []
    families = [str(row.get("family")) for row in summary.get("family_summaries", [])]
    for arm_id in fixed_arms:
        vs_base = _effect(summary, arm_id, baseline)
        if not vs_base or int(vs_base.get("net_wins") or 0) <= 0 or int(vs_base.get("catastrophes_added") or 0) != 0:
            continue
        strong_families: list[str] = []
        family_net_total = 0
        for family in families:
            fb = _family_effect(summary, family, arm_id, baseline)
            fr = _family_effect(summary, family, arm_id, random_control)
            if not fb or not fr:
                continue
            family_net_total += int(fb.get("net_wins") or 0)
            if (
                int(fb.get("net_wins") or 0) >= 2
                and int(fr.get("net_wins") or 0) >= 1
                and int(fb.get("catastrophes_added") or 0) == 0
            ):
                strong_families.append(family)
        if len(strong_families) >= 2:
            conditional.append((len(strong_families), family_net_total, arm_id, sorted(strong_families)))
    conditional.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if conditional:
        _, _, winner, strong_families = conditional[0]
        return {
            "verdict": "S1_R2_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL",
            "reason": f"{winner} showed preregistered strong effects in multiple task families without meeting the universal aggregate threshold.",
            "winning_arm_id": winner,
            "strong_families": strong_families,
            "matched_task_count": matched,
            "tier_a_architecture_claim": False,
            "routing_hypothesis_supported": True,
            "protocol_valid_for_primary_claim": True,
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": underpowered,
        }

    effects = {arm_id: _effect(summary, arm_id, baseline) for arm_id in fixed_arms}
    both_materially_worse = bool(fixed_arms) and all(
        effect is not None and int(effect.get("net_wins") or 0) <= -3
        for effect in effects.values()
    )
    both_catastrophic_without_positive = bool(fixed_arms) and all(
        effect is not None
        and int(effect.get("catastrophes_added") or 0) >= 1
        and int(effect.get("net_wins") or 0) <= 0
        for effect in effects.values()
    )
    if both_materially_worse or both_catastrophic_without_positive:
        return {
            "verdict": "S1_R2_FIXED_ORDER_NEGATIVE_OR_HARMFUL",
            "reason": "Both production fixed-order arms crossed the preregistered negative/harmful threshold versus the best-single baseline.",
            "winning_arm_id": None,
            "matched_task_count": matched,
            "tier_a_architecture_claim": False,
            "protocol_valid_for_primary_claim": True,
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": underpowered,
        }

    return {
        "verdict": "S1_R2_SCREEN_NON_DECISIVE",
        "reason": "No fixed arm crossed the aggregate, category-conditional, or harmful S1-R2 threshold.",
        "winning_arm_id": None,
        "matched_task_count": matched,
        "tier_a_architecture_claim": False,
        "protocol_valid_for_primary_claim": True,
        "full_power_cluster_requirement": full_power_clusters,
        "cannot_rule_out_target_effect": underpowered,
    }


def derive_s1_verdict(summary: dict[str, Any], *, full_power_clusters: int | None) -> dict[str, Any]:
    matched = int(summary.get("matched_task_count") or 0)
    underpowered = bool(full_power_clusters is not None and matched < int(full_power_clusters))
    if summary.get("protocol_valid_for_primary_claim") is not True:
        return _invalid_verdict(summary, full_power_clusters)
    if summary.get("protocol_revision") == S1_R2_PROTOCOL:
        return _derive_r2(summary, full_power_clusters=full_power_clusters, underpowered=underpowered)
    return _derive_r1(summary, full_power_clusters=full_power_clusters, underpowered=underpowered)
