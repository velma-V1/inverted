from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .domain import Candidate, TaskCase
from .oracle import get_path
from .test2_analysis import capability_matrix


def structured_failure_feedback(task: TaskCase, candidate: Candidate | None, failed_ids: list[str]) -> dict[str, Any]:
    req_by_id = {req.id: req for req in task.requirements}
    rows: list[dict[str, Any]] = []
    actions = list(candidate.actions) if candidate is not None else []
    for rid in failed_ids:
        req = req_by_id.get(rid)
        if req is None:
            continue
        if req.kind in {"equal", "preserve"}:
            observed: Any = {"state_value": get_path(candidate.state.data, req.path) if candidate is not None else None}
            admissible: Any = [req.expected]
        elif req.kind == "action_absent":
            matches = [a.to_dict() for a in actions if a.op == req.path and (req.expected is None or a.path == req.expected)]
            observed = {"matching_actions": matches}
            admissible = {"condition": "no_matching_action", "op": req.path, "path": req.expected}
        elif req.kind == "action_present":
            matches = [a.to_dict() for a in actions if a.op == req.path and (req.expected is None or a.path == req.expected)]
            observed = {"matching_actions": matches}
            admissible = {"condition": "matching_action_present", "op": req.path, "path": req.expected}
        elif req.kind == "action_before":
            before_indices = [i for i, a in enumerate(actions) if a.op == req.path]
            after_indices = [i for i, a in enumerate(actions) if a.op == str(req.expected)]
            observed = {"before_indices": before_indices, "after_indices": after_indices}
            admissible = {"condition": "before", "before_op": req.path, "after_op": req.expected}
        else:
            observed = {"unsupported_kind": req.kind}
            admissible = None
        rows.append({
            "id": rid,
            "kind": req.kind,
            "path": req.path,
            "observed": observed,
            "expected": req.expected,
            "admissible": admissible,
            "critical": bool(req.critical),
        })
    return {"failed_requirements": rows}


def _audit_truth(row: dict[str, Any]) -> bool:
    if isinstance(row.get("gold_accept"), bool):
        return bool(row["gold_accept"])
    return bool(row.get("oracle_success"))


def audit_confusion_by_model(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("model"))].append(row)
    out: list[dict[str, Any]] = []
    for model, group in sorted(grouped.items()):
        tp = tn = fp = fn = abstain_valid = abstain_invalid = 0
        for row in group:
            truth = _audit_truth(row)
            accept = row.get("accept")
            if accept is True and truth:
                tp += 1
            elif accept is False and not truth:
                tn += 1
            elif accept is True and not truth:
                fp += 1
            elif accept is False and truth:
                fn += 1
            elif truth:
                abstain_valid += 1
            else:
                abstain_invalid += 1
        valid_n = tp + fn + abstain_valid
        invalid_n = tn + fp + abstain_invalid
        specificity = tn / invalid_n if invalid_n else 0.0
        valid_recall = tp / valid_n if valid_n else 0.0
        false_accept_rate = fp / invalid_n if invalid_n else 0.0
        false_reject_rate = fn / valid_n if valid_n else 0.0
        risk_score = (2.0 * specificity + valid_recall) / 3.0
        out.append({
            "model": model,
            "n": len(group),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "abstain_valid": abstain_valid, "abstain_invalid": abstain_invalid,
            "specificity": specificity,
            "valid_accept_recall": valid_recall,
            "false_accept_rate": false_accept_rate,
            "false_reject_rate": false_reject_rate,
            "balanced_accuracy": (specificity + valid_recall) / 2.0,
            "risk_weighted_score": risk_score,
        })
    return out


def rank_auditors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = audit_confusion_by_model(rows)
    return sorted(
        ranked,
        key=lambda row: (
            -float(row["risk_weighted_score"]),
            float(row["false_accept_rate"]),
            -float(row["valid_accept_recall"]),
            str(row["model"]),
        ),
    )


def balanced_role_model_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_model_role: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for row in rows:
        model = row.get("model")
        role = row.get("role")
        if model is None or role is None:
            continue
        by_model_role[(str(model), str(role))].append(bool(row.get("success")))
    model_roles: dict[str, dict[str, float]] = defaultdict(dict)
    for (model, role), values in by_model_role.items():
        model_roles[model][role] = sum(values) / len(values) if values else 0.0
    out: list[dict[str, Any]] = []
    for model, role_scores in sorted(model_roles.items()):
        scores = list(role_scores.values())
        out.append({
            "model": model,
            "roles_scored": len(role_scores),
            "balanced_role_score": sum(scores) / len(scores) if scores else 0.0,
            "role_scores": dict(sorted(role_scores.items())),
        })
    return sorted(out, key=lambda row: (-float(row["balanced_role_score"]), -int(row["roles_scored"]), str(row["model"])))


def select_stability_task_ids(rows: list[dict[str, Any]], max_cases: int = 8) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("task_id"))].append(row)
    scored: list[dict[str, Any]] = []
    for task_id, group in grouped.items():
        truth = _audit_truth(group[0])
        decisions = [row.get("accept") for row in group]
        counts = Counter(str(value) for value in decisions)
        majority = max(counts.values()) if counts else 0
        disagreement = 1.0 - (majority / len(decisions) if decisions else 1.0)
        false_accepts = sum(1 for row in group if not truth and row.get("accept") is True)
        false_rejects = sum(1 for row in group if truth and row.get("accept") is False)
        abstains = sum(1 for row in group if not isinstance(row.get("accept"), bool))
        score = (4 * false_accepts) + (2 * false_rejects) + (3 * disagreement) + abstains
        scored.append({
            "task_id": task_id,
            "oracle_success": truth,
            "gold_accept": truth,
            "disagreement_rate": disagreement,
            "false_accepts": false_accepts,
            "false_rejects": false_rejects,
            "abstains": abstains,
            "decision_sensitivity_score": score,
        })
    invalid = sorted((row for row in scored if not row["gold_accept"]), key=lambda r: (-float(r["decision_sensitivity_score"]), str(r["task_id"])))
    valid = sorted((row for row in scored if row["gold_accept"]), key=lambda r: (-float(r["decision_sensitivity_score"]), str(r["task_id"])))
    invalid_quota = min(len(invalid), max_cases // 2)
    valid_quota = min(len(valid), max_cases - invalid_quota)
    chosen = invalid[:invalid_quota] + valid[:valid_quota]
    remaining = [row for row in sorted(scored, key=lambda r: (-float(r["decision_sensitivity_score"]), str(r["task_id"]))) if row not in chosen]
    chosen.extend(remaining[: max(0, max_cases - len(chosen))])
    return sorted(chosen, key=lambda r: (-float(r["decision_sensitivity_score"]), str(r["task_id"])))


def _mean_success(rows: list[dict[str, Any]]) -> float:
    return sum(bool(row.get("success")) for row in rows) / len(rows) if rows else 0.0


def repair_factorial_effects(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cells[(str(row.get("feedback_style")), str(row.get("strategy")))].append(row)
    condition_rows: list[dict[str, Any]] = []
    for (feedback, strategy), group in sorted(cells.items()):
        condition_rows.append({
            "feedback_style": feedback,
            "strategy": strategy,
            "n": len(group),
            "success_rate": _mean_success(group),
            "mean_preservation_rate": sum(float(row.get("preservation_rate", 0.0) or 0.0) for row in group) / len(group) if group else 0.0,
            "mean_new_failures_introduced": sum(float(row.get("new_failures_introduced", 0.0) or 0.0) for row in group) / len(group) if group else 0.0,
        })
    rate = {(row["feedback_style"], row["strategy"]): float(row["success_rate"]) for row in condition_rows}
    raw_mean = sum(rate.get(("raw", strategy), 0.0) for strategy in ("regenerate", "targeted")) / 2.0
    structured_mean = sum(rate.get(("structured", strategy), 0.0) for strategy in ("regenerate", "targeted")) / 2.0
    regen_mean = sum(rate.get((feedback, "regenerate"), 0.0) for feedback in ("raw", "structured")) / 2.0
    targeted_mean = sum(rate.get((feedback, "targeted"), 0.0) for feedback in ("raw", "structured")) / 2.0
    interaction = (
        rate.get(("structured", "targeted"), 0.0)
        - rate.get(("structured", "regenerate"), 0.0)
        - rate.get(("raw", "targeted"), 0.0)
        + rate.get(("raw", "regenerate"), 0.0)
    )
    targeted_rows = [row for row in rows if row.get("strategy") == "targeted"]
    regen_rows = [row for row in rows if row.get("strategy") == "regenerate"]
    targeted_pres = sum(float(row.get("preservation_rate", 0.0) or 0.0) for row in targeted_rows) / len(targeted_rows) if targeted_rows else 0.0
    regen_pres = sum(float(row.get("preservation_rate", 0.0) or 0.0) for row in regen_rows) / len(regen_rows) if regen_rows else 0.0
    return {
        "condition_rows": condition_rows,
        "feedback_main_effect_pp": 100.0 * (structured_mean - raw_mean),
        "strategy_main_effect_pp": 100.0 * (targeted_mean - regen_mean),
        "interaction_pp": 100.0 * interaction,
        "targeted_preservation_advantage": targeted_pres - regen_pres,
    }


_PROGRESSIVE_ORDER = (
    "S0_BEST_SINGLE_ALL_ROLES",
    "S1_SPECIALIZE_FORMALIZER",
    "S2_SPECIALIZE_FORMALIZER_EXECUTOR",
    "S3_SPECIALIZE_FORMALIZER_EXECUTOR_REPAIR",
    "S4_FULL_SPECIALIZATION",
)


def progressive_compounding_effects(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task_pipeline = {(str(row.get("task_id")), str(row.get("pipeline"))): row for row in rows}
    task_ids = sorted({str(row.get("task_id")) for row in rows})
    out: list[dict[str, Any]] = []
    for before_name, after_name in zip(_PROGRESSIVE_ORDER, _PROGRESSIVE_ORDER[1:]):
        wins_created = wins_destroyed = preserved = unchanged_fail = 0
        matched = 0
        for task_id in task_ids:
            before = by_task_pipeline.get((task_id, before_name))
            after = by_task_pipeline.get((task_id, after_name))
            if before is None or after is None:
                continue
            matched += 1
            b = bool(before.get("success")); a = bool(after.get("success"))
            if not b and a:
                wins_created += 1
            elif b and not a:
                wins_destroyed += 1
            elif b and a:
                preserved += 1
            else:
                unchanged_fail += 1
        out.append({
            "from_pipeline": before_name,
            "to_pipeline": after_name,
            "matched_tasks": matched,
            "wins_created": wins_created,
            "wins_destroyed": wins_destroyed,
            "net_wins": wins_created - wins_destroyed,
            "wins_preserved": preserved,
            "failures_unchanged": unchanged_fail,
            "increment_pp": 100.0 * (wins_created - wins_destroyed) / matched if matched else 0.0,
        })
    return out


def build_layered_capability_outputs(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "role": capability_matrix(rows, ("role", "model")),
        "family": capability_matrix([r for r in rows if r.get("family") is not None], ("role", "family", "model")),
        "fault": capability_matrix([r for r in rows if r.get("fault") is not None], ("role", "fault", "model")),
        "complexity": capability_matrix([r for r in rows if r.get("complexity") is not None], ("role", "complexity", "model")),
        "representation": capability_matrix([r for r in rows if r.get("representation") is not None], ("role", "representation", "model")),
    }
