from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections import defaultdict
from typing import Any, Iterable


def grouped_fold(task_id: str, causal_twin_id: str | None = None, folds: int = 5) -> int:
    if folds < 2:
        raise ValueError("folds must be >= 2")
    group = causal_twin_id or task_id
    digest = hashlib.sha256(str(group).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % folds


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


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _aggregate_candidate(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [_as_bool(row.get("success")) for row in rows]
    observed_success = [value for value in successes if value is not None]
    catastrophes = [_as_bool(row.get("catastrophic")) for row in rows]
    observed_cat = [value for value in catastrophes if value is not None]
    calls = [_as_float(row.get("calls", row.get("physical_calls"))) for row in rows]
    tokens = [_as_float(row.get("tokens")) for row in rows]
    latency = [_as_float(row.get("latency_ms", row.get("elapsed_ms"))) for row in rows]

    def mean_known(values: list[float | None]) -> float | None:
        known = [value for value in values if value is not None]
        return statistics.fmean(known) if known else None

    return {
        "candidate": name,
        "rows": len(rows),
        "verified_successes": sum(1 for value in observed_success if value),
        "verified_failures": sum(1 for value in observed_success if value is False),
        "verified_success_rate": statistics.fmean(observed_success) if observed_success else None,
        "catastrophe_rate": statistics.fmean(observed_cat) if observed_cat else 0.0,
        "calls": mean_known(calls),
        "tokens": mean_known(tokens),
        "latency_ms": mean_known(latency),
        "fully_costed": all(value is not None for value in calls + tokens + latency) if rows else False,
    }


def _explicit_policy_name(row: dict[str, Any]) -> str | None:
    for key in ("policy", "policy_id", "stack_order", "fixed_order", "pipeline_order", "stack_id"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def score_fixed_policies(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score only rows with an explicit fixed-policy/order identity.

    A single observed action/component is not a fixed policy and must never be
    promoted into one merely because historical rows lack a policy field.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        name = _explicit_policy_name(row)
        if name is None:
            continue
        grouped[name].append(row)
    return sorted(
        (_aggregate_candidate(name, items) for name, items in grouped.items()),
        key=lambda row: (
            -(row["verified_success_rate"] if row["verified_success_rate"] is not None else -1.0),
            row["catastrophe_rate"] if row["catastrophe_rate"] is not None else math.inf,
            row["candidate"],
        ),
    )


def score_component_outcomes(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain useful historical per-component outcome summaries without calling them policies."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        name = str(row.get("action") or row.get("component") or "unknown")
        grouped[name].append(row)
    return sorted(
        (
            {"summary_type": "historical_component_outcome", **_aggregate_candidate(name, items)}
            for name, items in grouped.items()
        ),
        key=lambda row: (
            -(row["verified_success_rate"] if row["verified_success_rate"] is not None else -1.0),
            row["catastrophe_rate"] if row["catastrophe_rate"] is not None else math.inf,
            row["candidate"],
        ),
    )


def derive_fixed_policy_candidates_from_comparisons(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Promote explicit Test-2 order rankings into S1 hypotheses without upgrading simulation to proof."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in rows:
        row = dict(raw)
        source_file = str(row.get("source_file") or "").replace("\\", "/")
        order = row.get("order")
        if not source_file.endswith("order/order-ranking.csv") or order in (None, ""):
            continue
        source_id = str(row.get("source_id") or "")
        key = (source_id, str(order))
        if key in seen:
            continue
        seen.add(key)
        try:
            rank = int(float(str(row.get("rank")))) if row.get("rank") not in (None, "") else None
        except (TypeError, ValueError):
            rank = None
        out.append({
            "candidate": str(order),
            "rank": rank,
            "components": row.get("components"),
            "source_id": source_id,
            "source_file": source_file,
            "causal_status": row.get("causal_status"),
            "changes_upstream_prompt": _as_bool(row.get("changes_upstream_prompt")),
            "rows": int(float(str(row.get("n")))) if row.get("n") not in (None, "") else None,
            "simulated_success_rate": _as_float(row.get("simulated_success_rate")),
            "simulated_blocked_rate": _as_float(row.get("blocked_rate")),
            "simulated_catastrophe_rate": _as_float(row.get("catastrophic_rate")),
            "verified_successes": None,
            "verified_failures": None,
            "verified_success_rate": None,
            "catastrophe_rate": None,
            "calls": None,
            "tokens": None,
            "latency_ms": None,
            "fully_costed": False,
            "evidence_basis": "MODEL_FREE_ORDER_RANKING_HYPOTHESIS",
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


def _best_action_mapping(rows: list[dict[str, Any]]) -> dict[str, str]:
    buckets: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for row in rows:
        signature = str(row.get("failure_signature") or row.get("failure_class") or "UNKNOWN")
        action = str(row.get("action") or row.get("component") or "unknown")
        success = _as_bool(row.get("success"))
        if success is not None:
            buckets[(signature, action)].append(success)
    candidates: dict[str, list[tuple[float, int, str]]] = defaultdict(list)
    for (signature, action), values in buckets.items():
        candidates[signature].append((statistics.fmean(values), len(values), action))
    mapping: dict[str, str] = {}
    for signature, values in candidates.items():
        values.sort(key=lambda item: (-item[0], -item[1], item[2]))
        mapping[signature] = values[0][2]
    return mapping


def choose_failure_conditioned_policy(
    rows: Iterable[dict[str, Any]],
    holdout_fold: int,
    *,
    folds: int = 5,
) -> dict[str, Any]:
    all_rows = [dict(row) for row in rows]
    train: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for row in all_rows:
        fold = grouped_fold(str(row.get("task_id", "")), row.get("causal_twin_id"), folds)
        (holdout if fold == holdout_fold else train).append(row)
    mapping = _best_action_mapping(train)
    scored = 0
    successes = 0
    misses = 0
    predictions: list[dict[str, Any]] = []
    for row in holdout:
        signature = str(row.get("failure_signature") or row.get("failure_class") or "UNKNOWN")
        predicted = mapping.get(signature)
        observed_action = str(row.get("action") or row.get("component") or "unknown")
        outcome = _as_bool(row.get("success"))
        replayable = predicted is not None and predicted == observed_action and outcome is not None
        if replayable:
            scored += 1
            successes += int(bool(outcome))
        else:
            misses += 1
        predictions.append({
            "task_id": row.get("task_id"),
            "causal_twin_id": row.get("causal_twin_id"),
            "failure_signature": signature,
            "predicted_action": predicted,
            "observed_action": observed_action,
            "replayable": replayable,
            "success": outcome if replayable else None,
        })
    return {
        "holdout_fold": holdout_fold,
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "mapping": mapping,
        "replayable_holdout_rows": scored,
        "unresolved_holdout_rows": misses,
        "verified_success_rate": (successes / scored) if scored else None,
        "predictions": predictions,
    }


def score_grouped_policy(rows: Iterable[dict[str, Any]], folds: int = 5) -> dict[str, Any]:
    all_rows = [dict(row) for row in rows]
    fold_results = [choose_failure_conditioned_policy(all_rows, fold, folds=folds) for fold in range(folds)]
    scored = sum(int(row["replayable_holdout_rows"]) for row in fold_results)
    success_sum = 0.0
    for row in fold_results:
        if row["verified_success_rate"] is not None:
            success_sum += row["verified_success_rate"] * row["replayable_holdout_rows"]
    return {
        "folds": folds,
        "rows": len(all_rows),
        "replayable_rows": scored,
        "coverage": scored / len(all_rows) if all_rows else 0.0,
        "verified_success_rate": success_sum / scored if scored else None,
        "fold_results": fold_results,
    }


def score_negative_controls(rows: Iterable[dict[str, Any]], seed: int = 20260901) -> list[dict[str, Any]]:
    """Classify negative controls without mistaking no-op identity subsets for interventions."""
    data = [dict(row) for row in rows]
    rng = random.Random(seed)
    actions = sorted({str(row.get("action") or row.get("component") or "unknown") for row in data})
    randomized = list(actions)
    rng.shuffle(randomized)
    substitution = {action: randomized[index] for index, action in enumerate(actions)}

    def identity_subset(selector: callable) -> tuple[int, int]:
        replayable = 0
        successes = 0
        for row in data:
            observed = str(row.get("action") or row.get("component") or "unknown")
            proposed = selector(row, observed)
            outcome = _as_bool(row.get("success"))
            if proposed == observed and outcome is not None:
                replayable += 1
                successes += int(bool(outcome))
        return replayable, successes

    random_identity_rows, random_identity_success = identity_subset(
        lambda row, observed: substitution.get(observed, observed)
    )
    retry_identity_rows, retry_identity_success = identity_subset(lambda row, observed: "retry")
    identity_actions = sorted(action for action, mapped in substitution.items() if action == mapped)

    results = [
        {
            "control": "random_action_switch",
            "seed": seed,
            "replayable_rows": 0,
            "verified_success_rate": None,
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "mapping": substitution,
            "identity_actions": identity_actions,
            "identity_subset_replayable_rows": random_identity_rows,
            "identity_subset_success_rate": (
                random_identity_success / random_identity_rows if random_identity_rows else None
            ),
            "reason": (
                "A true random switch changes the historical action and therefore requires an unobserved outcome. "
                "Rows where the shuffled mapping equals the observed action are a no-op identity subset, not evidence "
                "for the random-switch intervention."
            ),
        },
        {
            "control": "random_retry",
            "seed": seed,
            "replayable_rows": 0,
            "verified_success_rate": None,
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "identity_subset_replayable_rows": retry_identity_rows,
            "identity_subset_success_rate": (
                retry_identity_success / retry_identity_rows if retry_identity_rows else None
            ),
            "reason": (
                "Applying retry to historical non-retry states changes the action and requires an unobserved outcome. "
                "Observed retry rows form only an identity subset and cannot estimate the random-retry intervention."
            ),
        },
        {
            "control": "random_extra_model_call",
            "seed": seed,
            "replayable_rows": 0,
            "verified_success_rate": None,
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "reason": "extra model output is unobserved and Section 0 cannot create it",
        },
        {
            "control": "irrelevant_edge_case_or_skill",
            "seed": seed,
            "replayable_rows": 0,
            "verified_success_rate": None,
            "causal_status": "REQUIRES_NEW_INFERENCE",
            "reason": "counterfactual context mutation would change model input",
        },
    ]
    return results


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    metrics = (
        ("verified_success_rate", True),
        ("catastrophe_rate", False),
        ("calls", False),
        ("tokens", False),
        ("latency_ms", False),
    )
    if any(a.get(key) is None or b.get(key) is None for key, _ in metrics):
        return False
    no_worse = True
    strictly_better = False
    for key, maximize in metrics:
        av = float(a[key])
        bv = float(b[key])
        if maximize:
            if av < bv:
                no_worse = False
            if av > bv:
                strictly_better = True
        else:
            if av > bv:
                no_worse = False
            if av < bv:
                strictly_better = True
    return no_worse and strictly_better


def pareto_rank_candidates(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    data = [dict(row) for row in rows]
    out: list[dict[str, Any]] = []
    for index, row in enumerate(data):
        complete = all(row.get(key) is not None for key in ("verified_success_rate", "catastrophe_rate", "calls", "tokens", "latency_ms"))
        dominated_by = [other.get("candidate") for j, other in enumerate(data) if j != index and _dominates(other, row)]
        enriched = dict(row)
        enriched["fully_costed"] = complete
        enriched["pareto"] = (not dominated_by) if complete else None
        enriched["dominated_by"] = dominated_by
        out.append(enriched)
    return sorted(out, key=lambda row: (row.get("pareto") is not True, str(row.get("candidate", ""))))


def bootstrap_effect_ci(
    rows: Iterable[dict[str, Any]],
    *,
    iterations: int = 20000,
    seed: int = 20260901,
    alpha: float = 0.05,
) -> dict[str, Any]:
    data = [dict(row) for row in rows]
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for row in data:
        cluster = str(row.get("cluster_id") or row.get("causal_twin_id") or row.get("task_id") or "")
        effect = _as_float(row.get("effect"))
        if cluster and effect is not None:
            by_cluster[cluster].append(effect)
    cluster_effects = {cluster: statistics.fmean(values) for cluster, values in by_cluster.items()}
    values = list(cluster_effects.values())
    if len(values) < 2:
        return {
            "status": "INSUFFICIENT_VARIANCE_EVIDENCE",
            "clusters": len(values),
            "mean_effect": statistics.fmean(values) if values else None,
            "lower": None,
            "upper": None,
        }
    rng = random.Random(seed)
    samples: list[float] = []
    n = len(values)
    for _ in range(iterations):
        samples.append(statistics.fmean(values[rng.randrange(n)] for _ in range(n)))
    samples.sort()
    lower_index = max(0, min(len(samples) - 1, int((alpha / 2) * len(samples))))
    upper_index = max(0, min(len(samples) - 1, int((1 - alpha / 2) * len(samples)) - 1))
    return {
        "status": "OK",
        "clusters": n,
        "mean_effect": statistics.fmean(values),
        "cluster_sd": statistics.stdev(values),
        "iterations": iterations,
        "seed": seed,
        "alpha": alpha,
        "lower": samples[lower_index],
        "upper": samples[upper_index],
    }


def estimate_required_task_clusters(
    rows: Iterable[dict[str, Any]],
    *,
    target_effect: float,
    alpha: float = 0.05,
    target_power: float = 0.80,
) -> dict[str, Any]:
    del alpha, target_power
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        cluster = str(row.get("cluster_id") or row.get("causal_twin_id") or row.get("task_id") or "")
        effect = _as_float(row.get("effect"))
        if cluster and effect is not None:
            by_cluster[cluster].append(effect)
    effects = [statistics.fmean(values) for values in by_cluster.values()]
    if len(effects) < 2:
        return {
            "status": "INSUFFICIENT_VARIANCE_EVIDENCE",
            "clusters": len(effects),
            "cluster_sd": None,
            "target_effect": target_effect,
            "recommended_clusters": None,
        }
    sd = statistics.stdev(effects)
    if target_effect <= 0:
        raise ValueError("target_effect must be > 0")
    recommended = math.ceil(((1.959963984540054 + 0.8416212335729143) * sd / target_effect) ** 2)
    return {
        "status": "OK",
        "clusters": len(effects),
        "cluster_sd": sd,
        "target_effect": target_effect,
        "recommended_clusters": max(2, recommended),
        "formula": "ceil(((z_0.975 + z_0.80) * cluster_sd / target_effect) ** 2)",
    }


def build_candidate_s1_preregistration(power: dict[str, Any]) -> dict[str, Any]:
    recommended = power.get("recommended_clusters") if power.get("status") == "OK" else None
    return {
        "status": "CANDIDATE_ONLY_NOT_PREREGISTERED",
        "section": "S1_FIXED_STACK_ORDER",
        "holdout": "A",
        "tier_a_inference_authorized": False,
        "exact_budget": None,
        "recommended_task_clusters": recommended,
        "recommended_range": (
            [max(2, int(math.floor(recommended * 0.8))), int(math.ceil(recommended * 1.2))]
            if isinstance(recommended, int) else None
        ),
        "budget_freeze_requires_human_review": True,
        "power_evidence": power,
    }
