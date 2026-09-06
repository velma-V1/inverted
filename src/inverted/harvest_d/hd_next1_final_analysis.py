from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from .hd_next1_decisions import compile_model_ownership, compile_negative_transfer, router_is_promotable
from .hd_next1_statistics import holm_rejections


def _paired(rows: Iterable[Mapping[str, Any]], left_role: str, right_role: str, *, model_key: str = "SMALL_A") -> tuple[int, int, int, dict[str, tuple[int, int, int]]]:
    by_case: dict[str, dict[str, bool]] = {}
    partitions: dict[str, str] = {}
    for row in rows:
        if str(row.get("model_key")) != model_key:
            continue
        role = str(row.get("treatment_role") or "")
        if role not in {left_role, right_role}:
            continue
        case_id = str(row.get("case_id") or "")
        if not case_id:
            continue
        by_case.setdefault(case_id, {})[role] = bool(row.get("verified_outcome_correct"))
        partitions[case_id] = str(row.get("partition") or "UNKNOWN")
    left_only = right_only = matched_n = 0
    by_partition: dict[str, list[int]] = {}
    for case_id, values in by_case.items():
        if left_role not in values or right_role not in values:
            continue
        matched_n += 1
        l_only = int(values[left_role] and not values[right_role])
        r_only = int(values[right_role] and not values[left_role])
        left_only += l_only
        right_only += r_only
        stats = by_partition.setdefault(partitions.get(case_id, "UNKNOWN"), [0, 0, 0])
        stats[0] += l_only
        stats[1] += r_only
        stats[2] += 1
    return left_only, right_only, matched_n, {key: tuple(value) for key, value in by_partition.items()}


def _model_pairs(rows: Iterable[Mapping[str, Any]]) -> tuple[int, int, int, dict[str, tuple[int, int, int]]]:
    by_case: dict[str, dict[str, bool]] = {}
    partitions: dict[str, str] = {}
    for row in rows:
        if str(row.get("treatment_role") or "") != "CONFIRM_PROMOTED_POLICY":
            continue
        model = str(row.get("model_key") or "")
        if model not in {"SMALL_A", "QWEN"}:
            continue
        case_id = str(row.get("case_id") or "")
        by_case.setdefault(case_id, {})[model] = bool(row.get("verified_outcome_correct"))
        partitions[case_id] = str(row.get("partition") or "UNKNOWN")
    qwen_only = small_only = matched_n = 0
    by_partition: dict[str, list[int]] = {}
    for case_id, values in by_case.items():
        if "SMALL_A" not in values or "QWEN" not in values:
            continue
        matched_n += 1
        q_only = int(values["QWEN"] and not values["SMALL_A"])
        s_only = int(values["SMALL_A"] and not values["QWEN"])
        qwen_only += q_only
        small_only += s_only
        stats = by_partition.setdefault(partitions.get(case_id, "UNKNOWN"), [0, 0, 0])
        stats[0] += q_only
        stats[1] += s_only
        stats[2] += 1
    return qwen_only, small_only, matched_n, {key: tuple(value) for key, value in by_partition.items()}


def _upper_tail(k: int, n: int, p: float) -> float:
    if n <= 0 or not 0 <= k <= n:
        return 1.0
    return sum(math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1))


def _partitions_do_not_reverse(stats: Mapping[str, tuple[int, int, int]], *, expected_left_advantage: bool) -> bool:
    for left_only, right_only, n in stats.values():
        if n <= 0:
            continue
        if expected_left_advantage and right_only > left_only:
            return False
        if not expected_left_advantage and left_only > right_only:
            return False
    return True


def _minimum_support(rows: tuple[Mapping[str, Any], ...], development_freeze: Mapping[str, Any]) -> dict[str, object]:
    retained = tuple(str(item) for item in (development_freeze.get("retained_components") or ()))
    ablation_left, ablation_right, n_ablation, ablation_parts = _paired(
        rows, "CONFIRM_PROMOTED_POLICY", "CONFIRM_STRONGEST_CHALLENGER"
    )
    raw_left, raw_right, n_raw, raw_parts = _paired(rows, "CONFIRM_PROMOTED_POLICY", "CONFIRM_RAW_BASELINE")

    if not retained:
        return {
            "state": "REDUNDANT",
            "claim": "MINIMUM_SUFFICIENT",
            "action": "KEEP_ZERO_OPTIONAL_SUPPORT",
            "retained_components": [],
            "matched_ablation_cases": n_ablation,
        }

    p_ablation = _upper_tail(ablation_left, n_ablation, 0.05)
    p_joint = _upper_tail(raw_left, n_raw, 0.05)
    significant = holm_rejections((p_ablation, p_joint), 0.05) if n_ablation and n_raw else (False, False)
    necessity = bool(
        significant[0]
        and ablation_left > ablation_right
        and _partitions_do_not_reverse(ablation_parts, expected_left_advantage=True)
    )
    joint_attack = bool(
        significant[1]
        and raw_left > raw_right
        and _partitions_do_not_reverse(raw_parts, expected_left_advantage=True)
    )

    if len(retained) == 1 and necessity and joint_attack:
        return {
            "state": "REQUIRED",
            "claim": "MINIMUM_SUFFICIENT",
            "action": "KEEP",
            "retained_components": list(retained),
            "strongest_ablation_component": development_freeze.get("strongest_ablation_component"),
            "full_only_wins": ablation_left,
            "ablation_only_wins": ablation_right,
            "joint_full_only_wins": raw_left,
            "joint_only_wins": raw_right,
        }

    return {
        "state": "UNRESOLVED",
        "claim": "SMALLEST_DEFENSIBLE_TESTED_PACKET",
        "action": "KEEP_PENDING_COMPONENT_LEVEL_CONFIRMATION",
        "retained_components": list(retained),
        "full_only_wins": ablation_left,
        "ablation_only_wins": ablation_right,
        "joint_full_only_wins": raw_left,
        "joint_only_wins": raw_right,
        "reason": "minimum-sufficient label requires protected proof for every retained component plus a joint-removal attack",
    }


def _boundary_report(rows: tuple[Mapping[str, Any], ...], development_freeze: Mapping[str, Any]) -> dict[str, object]:
    extra_only, minimal_only, matched_n, parts = _paired(
        rows, "CONFIRM_NEGATIVE_TRANSFER_CONTROL", "CONFIRM_PROMOTED_POLICY"
    )
    decision = compile_negative_transfer(
        extra_only_wins=extra_only,
        minimal_only_wins=minimal_only,
        matched_n=matched_n,
    )
    boundary = development_freeze.get("candidate_boundary")
    router_promoted = False
    if isinstance(boundary, dict):
        fresh = parts.get("hd-next1-fresh", (0, 0, 0))
        sealed = parts.get("hd-next1-sealed", (0, 0, 0))
        direction = lambda row: (row[0] > row[1]) - (row[0] < row[1])
        fresh_direction = direction(fresh)
        sealed_direction = direction(sealed)
        reproduced = fresh_direction != 0 and sealed_direction in {0, fresh_direction}
        router_promoted = router_is_promotable(
            predicate_is_pre_outcome=bool(boundary.get("predicate_is_pre_outcome")),
            frozen_before_confirmation=bool(boundary.get("frozen_before_confirmation")),
            fresh_reproduced=reproduced,
            sealed_reproduced=reproduced,
            absolute_improvement=abs(extra_only - minimal_only) / matched_n if matched_n else 0.0,
            prevents_material_safety_regression=bool(boundary.get("prevents_material_safety_regression", False)),
        )
    return {
        "state": decision.state,
        "action": decision.action,
        "detail": decision.detail,
        "extra_only_wins": extra_only,
        "minimal_only_wins": minimal_only,
        "matched_cases": matched_n,
        "router_promoted": router_promoted,
        "candidate_boundary": boundary,
    }


def analyze_protected_evidence(rows: Iterable[Mapping[str, Any]], development_freeze: Mapping[str, Any]) -> dict[str, object]:
    protected = tuple(dict(row) for row in rows if str(row.get("stage", "")).startswith("T6_"))
    qwen_only, small_only, matched_n, model_parts = _model_pairs(protected)
    if matched_n:
        model = compile_model_ownership(qwen_only_wins=qwen_only, matched_n=matched_n)
        if any(part_n and q_only / part_n > 0.05 for q_only, _s_only, part_n in model_parts.values()):
            model_state = "UNRESOLVED"
            model_action = "RETAIN_BOUNDED_QWEN_ESCALATION"
            model_detail = "fresh or sealed partition contains a material Qwen-only loss rate"
        else:
            model_state, model_action, model_detail = model.state, model.action, model.detail
    else:
        model_state, model_action, model_detail = "UNRESOLVED", "RETAIN_BOUNDED_QWEN_ESCALATION", "no matched protected model evidence"

    return {
        "Q-MODEL-SUBSTITUTION": {
            "state": model_state,
            "action": model_action,
            "detail": model_detail,
            "qwen_only_wins": qwen_only,
            "small_a_only_wins": small_only,
            "matched_cases": matched_n,
        },
        "Q-MINIMUM-SUPPORT": _minimum_support(protected, development_freeze),
        "Q-NEGATIVE-TRANSFER-BOUNDARY": _boundary_report(protected, development_freeze),
    }
