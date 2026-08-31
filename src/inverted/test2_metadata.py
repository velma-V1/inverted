from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from typing import Any

from .test2_analysis import capability_matrix
from .test2_local_analysis import (
    audit_confusion_by_model,
    balanced_role_model_scores,
    progressive_compounding_effects,
    repair_factorial_effects,
)


def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p) / n) + z2 / (4.0 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def _capability_with_ci(rows: list[dict[str, Any]], dims: tuple[str, ...]) -> list[dict[str, Any]]:
    out = capability_matrix(rows, dims)
    for row in out:
        n = int(row.get("n") or 0)
        successes = int(row.get("successes") or round(float(row.get("success_rate", 0.0)) * n))
        low, high = _wilson(successes, n)
        row["ci95_low"] = low
        row["ci95_high"] = high
        row["ci95_width"] = high - low
    return out


def _model_efficiency(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in calls:
        groups[(str(row.get("role")), str(row.get("model")))].append(row)
    out: list[dict[str, Any]] = []
    for (role, model), group in sorted(groups.items()):
        physical = [row for row in group if not row.get("cache_hit")]
        def total(field: str) -> float:
            return sum(float(row.get(field) or 0.0) for row in physical)
        latency = total("latency_s")
        eval_s = total("eval_duration_s")
        load_s = total("load_duration_s")
        prompt_s = total("prompt_eval_duration_s")
        tokens = int(total("total_tokens"))
        out.append({
            "role": role,
            "model": model,
            "logical_calls": len(group),
            "physical_calls": len(physical),
            "cache_hits": len(group) - len(physical),
            "input_tokens": int(total("input_tokens")),
            "output_tokens": int(total("output_tokens")),
            "total_tokens": tokens,
            "wall_latency_s": latency,
            "load_duration_s": load_s,
            "prompt_eval_duration_s": prompt_s,
            "eval_duration_s": eval_s,
            "unattributed_latency_s": max(0.0, latency - load_s - prompt_s - eval_s),
            "tokens_per_eval_second": tokens / eval_s if eval_s > 0 else None,
            "cold_load_fraction": load_s / latency if latency > 0 else None,
        })
    return out


def _call_lineage(raw: dict[str, Any]) -> list[dict[str, Any]]:
    prompts = {str(row.get("call_identity")): row for row in raw.get("prompts", [])}
    responses = {str(row.get("call_identity")): row for row in raw.get("responses", [])}
    calls = {str(row.get("call_identity")): row for row in raw.get("model_calls", [])}
    identities = sorted(set(prompts) | set(responses) | set(calls))
    out = []
    for identity in identities:
        prompt_row = prompts.get(identity, {})
        response_row = responses.get(identity, {})
        call_row = calls.get(identity, {})
        prompt_text = str(prompt_row.get("serialized") or json.dumps(prompt_row.get("messages"), sort_keys=True, ensure_ascii=False))
        response_text = str(response_row.get("text") or "")
        pb = prompt_text.encode("utf-8")
        rb = response_text.encode("utf-8")
        out.append({
            "call_identity": identity,
            "phase": call_row.get("phase") or prompt_row.get("phase"),
            "task_id": call_row.get("task_id") or prompt_row.get("task_id"),
            "model": call_row.get("model") or prompt_row.get("model"),
            "role": call_row.get("role") or prompt_row.get("role"),
            "cache_hit": bool(call_row.get("cache_hit", False)),
            "prompt_sha256": hashlib.sha256(pb).hexdigest(),
            "response_sha256": hashlib.sha256(rb).hexdigest(),
            "prompt_chars": len(prompt_text),
            "prompt_bytes": len(pb),
            "response_chars": len(response_text),
            "response_bytes": len(rb),
        })
    return out


def _response_contract_health(raw: dict[str, Any]) -> list[dict[str, Any]]:
    calls = {str(row.get("call_identity")): row for row in raw.get("model_calls", [])}
    groups: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: Counter())
    for row in raw.get("responses", []):
        identity = str(row.get("call_identity"))
        call = calls.get(identity, {})
        key = (str(row.get("role") or call.get("role")), str(row.get("model") or call.get("model")))
        text = str(row.get("text") or "")
        groups[key]["n"] += 1
        if not text.strip():
            groups[key]["empty"] += 1
            continue
        try:
            value = json.loads(text)
            groups[key]["json_parse_ok"] += 1
            if isinstance(value, dict):
                groups[key]["object_ok"] += 1
            else:
                groups[key]["wrong_top_level"] += 1
        except Exception:
            groups[key]["json_parse_fail"] += 1
    return [{"role": role, "model": model, **dict(counts)} for (role, model), counts in sorted(groups.items())]


def _repair_factorial_expected_models(trials: list[dict[str, Any]], configured_models: list[str]) -> set[str]:
    configured = set(configured_models)
    screen_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trials:
        if row.get("phase") == "repair_screen" and row.get("model") in configured:
            screen_groups[str(row["model"])].append(row)
    if screen_groups:
        ranked = sorted(
            screen_groups,
            key=lambda model: (
                -(sum(bool(r.get("success")) for r in screen_groups[model]) / len(screen_groups[model])),
                -sum(float(r.get("preservation_rate", 0.0) or 0.0) for r in screen_groups[model]),
                model,
            ),
        )
        return set(ranked[:3])
    return {
        str(row.get("model"))
        for row in trials
        if row.get("phase") == "repair_factorial" and row.get("model") in configured
    }


def _matrix_coverage(trials: list[dict[str, Any]], configured_models: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in trials:
        evaluation_id = row.get("evaluation_id")
        if evaluation_id is None:
            continue
        groups[(str(row.get("phase")), str(evaluation_id))].append(row)
    out = []
    configured_expected = set(configured_models)
    repair_expected = _repair_factorial_expected_models(trials, configured_models)
    all_model_phases = {"formalization", "execution", "auditing", "repair_screen", "stability"}
    for (phase, evaluation_id), group in sorted(groups.items()):
        if phase in all_model_phases:
            expected = configured_expected
            matched_phase = True
        elif phase == "repair_factorial":
            expected = repair_expected
            matched_phase = True
        else:
            expected = set()
            matched_phase = False
        observed_all = {str(row.get("model")) for row in group if row.get("model") is not None}
        observed = observed_all & expected if matched_phase else observed_all
        out.append({
            "phase": phase,
            "evaluation_id": evaluation_id,
            "rows": len(group),
            "observed_models": sorted(observed_all),
            "expected_models": sorted(expected) if matched_phase else [],
            "missing_models": sorted(expected - observed) if matched_phase else [],
            "unexpected_models": sorted(observed_all - expected) if matched_phase else [],
            "duplicate_models": sorted(model for model, count in Counter(str(row.get("model")) for row in group).items() if count > 1),
            "matched_complete": (observed == expected and not (observed_all - expected)) if matched_phase else None,
        })
    return out


def _contamination_audit(raw: dict[str, Any], trials: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden = (
        "hidden_gold_success", "gold_accept", "semantic_issues", "semantic_clean",
        "injected_faults", "oracle_success", "benchmark_gold", "ground_truth",
    )
    hits = []
    for row in raw.get("prompts", []):
        text = str(row.get("serialized") or json.dumps(row.get("messages"), sort_keys=True, ensure_ascii=False)).lower()
        found = [marker for marker in forbidden if marker.lower() in text]
        if found:
            hits.append({"call_identity": row.get("call_identity"), "markers": found})

    duplicate_condition_model = []
    seen: Counter[tuple[str, str, str]] = Counter()
    for row in trials:
        if row.get("evaluation_id") is not None and row.get("model") is not None:
            seen[(str(row.get("phase")), str(row["evaluation_id"]), str(row["model"]))] += 1
    for (phase, evaluation_id, model), count in sorted(seen.items()):
        if count > 1:
            duplicate_condition_model.append({"phase": phase, "evaluation_id": evaluation_id, "model": model, "count": count})

    call_ids = [str(row.get("call_identity")) for row in raw.get("model_calls", []) if row.get("call_identity")]
    prompt_ids = [str(row.get("call_identity")) for row in raw.get("prompts", []) if row.get("call_identity")]
    response_ids = [str(row.get("call_identity")) for row in raw.get("responses", []) if row.get("call_identity")]
    return {
        "forbidden_prompt_marker_hits": hits,
        "hidden_label_leak_free": not hits,
        "duplicate_evaluation_model_rows": duplicate_condition_model,
        "unique_model_call_identity": len(call_ids) == len(set(call_ids)),
        "orphan_prompt_call_ids": sorted(set(prompt_ids) - set(call_ids)),
        "orphan_response_call_ids": sorted(set(response_ids) - set(call_ids)),
        "missing_prompt_for_call_ids": sorted(set(call_ids) - set(prompt_ids)),
        "missing_response_for_call_ids": sorted(set(call_ids) - set(response_ids)),
        "physical_call_rows": sum(1 for row in raw.get("model_calls", []) if not row.get("cache_hit")),
        "cache_hit_rows": sum(1 for row in raw.get("model_calls", []) if row.get("cache_hit")),
    }


def _system_decision_confusion(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trials:
        if isinstance(row.get("runtime_allowed"), bool) and isinstance(row.get("hidden_gold_success"), bool):
            groups[str(row.get("pipeline") or row.get("phase"))].append(row)
    out = []
    for name, group in sorted(groups.items()):
        tp = tn = fp = fn = 0
        for row in group:
            decision = bool(row["runtime_allowed"]); truth = bool(row["hidden_gold_success"])
            if decision and truth: tp += 1
            elif not decision and not truth: tn += 1
            elif decision and not truth: fp += 1
            else: fn += 1
        n = len(group); correct = tp + tn
        low, high = _wilson(correct, n)
        invalid = fp + tn; valid = tp + fn
        out.append({
            "decision_surface": name, "n": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "accuracy": correct / n if n else 0.0, "ci95_low": low, "ci95_high": high,
            "false_accept_rate": fp / invalid if invalid else 0.0,
            "false_reject_rate": fn / valid if valid else 0.0,
        })
    return out


def enrich_test2_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Add derived metadata from already-collected evidence only.

    This function performs no model, network, or external calls. It is safe to
    rerun after the experiment and therefore cannot contaminate inference.
    """
    raw = evidence.setdefault("raw", {})
    trials = list(raw.get("trials", []) or [])
    model_calls = list(raw.get("model_calls", []) or [])
    configured = list(((evidence.get("provenance") or {}).get("config") or {}).get("local", {}).get("models", []) or [])

    discovery = [row for row in trials if row.get("role") in {"formalizer", "executor", "auditor", "repairer"}]
    audit_rows = [row for row in trials if row.get("phase") == "auditing" and row.get("role") == "auditor"]
    repair_rows = [row for row in trials if row.get("phase") == "repair_factorial"]
    holdout_rows = [row for row in trials if row.get("phase") == "progressive_holdout"]

    models = evidence.setdefault("models", {})
    models["auditor_confusion"] = audit_confusion_by_model(audit_rows)
    for row in models["auditor_confusion"]:
        low, high = _wilson(int(row.get("tp", 0)) + int(row.get("tn", 0)), int(row.get("n", 0)))
        row["accuracy_ci95_low"] = low; row["accuracy_ci95_high"] = high
    models["balanced_role_scores"] = balanced_role_model_scores(discovery)
    models["layered_capability_role"] = _capability_with_ci(discovery, ("role", "model"))
    models["layered_capability_family"] = _capability_with_ci([r for r in discovery if r.get("family") is not None], ("role", "family", "model"))
    models["layered_capability_complexity"] = _capability_with_ci([r for r in discovery if r.get("complexity") is not None], ("role", "complexity", "model"))
    models["layered_capability_fault"] = _capability_with_ci([r for r in discovery if r.get("fault") is not None], ("role", "fault", "model"))
    models["layered_capability_representation"] = _capability_with_ci([r for r in discovery if r.get("representation") is not None], ("role", "representation", "model"))
    models["model_efficiency"] = _model_efficiency(model_calls)

    effects = evidence.setdefault("effects", {})
    effects["repair_factorial_summary"] = [repair_factorial_effects(repair_rows)] if repair_rows else []
    effects["progressive_model_compounding"] = progressive_compounding_effects(holdout_rows)
    effects["system_decision_confusion"] = _system_decision_confusion(trials)

    diagnostics = evidence.setdefault("diagnostics", {})
    diagnostics["contamination_audit"] = _contamination_audit(raw, trials)
    diagnostics["call_lineage"] = _call_lineage(raw)
    diagnostics["response_contract_health"] = _response_contract_health(raw)
    diagnostics["matrix_coverage"] = _matrix_coverage(trials, configured)
    diagnostics["phase_counts"] = [
        {"phase": phase, "trial_rows": count}
        for phase, count in sorted(Counter(str(row.get("phase")) for row in trials).items())
    ]
    return evidence
