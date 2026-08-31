from __future__ import annotations

from typing import Any


def _metric(summary: dict[str, Any], arm: str, name: str, default: float = 0.0) -> float:
    value = summary.get("by_arm", {}).get(arm, {}).get(name)
    return default if value is None else float(value)


def _majority_positive(values: dict[str, float]) -> bool:
    if not values:
        return False
    return sum(v > 0 for v in values.values()) > len(values) / 2


def _all_positive(values: dict[str, float]) -> bool:
    return bool(values) and all(v > 0 for v in values.values())


def decide_verdict(summary: dict[str, Any], config: Any) -> dict[str, Any]:
    a_n = int(summary.get("by_arm", {}).get("A_DIRECT", {}).get("n", 0))
    d_n = int(summary.get("by_arm", {}).get("D_INVERTED", {}).get("n", 0))
    primary = summary.get("primary", {})
    independent_clusters = int(primary.get("independent_task_clusters", 0))
    minimum = int(config.minimum_primary_trials)
    if not bool(config.decisive) or independent_clusters < minimum:
        return {
            "verdict": "NON-DECISIVE",
            "reason": "Run is smoke/non-decisive or lacks preregistered minimum independent task clusters.",
            "observations": {
                "A_DIRECT": a_n,
                "D_INVERTED": d_n,
                "independent_task_clusters": independent_clusters,
                "minimum_independent_task_clusters": minimum,
            },
            "gates": [],
        }

    diff = float(primary.get("d_minus_a") or 0.0)
    ci = primary.get("ci95") or {}
    ci_low = ci.get("lower")
    ci_high = ci.get("upper")
    equal_diff = float(primary.get("equal_budget_diff") or 0.0)
    d_minus_b = float(primary.get("d_minus_b") or 0.0)
    d_rate = _metric(summary, "D_INVERTED", "success_rate")
    e_rate = _metric(summary, "E_RANDOM_AUDITOR", "success_rate")
    catastrophic_delta = _metric(summary, "D_INVERTED", "catastrophic_rate") - _metric(summary, "A_DIRECT", "catastrophic_rate")
    family_adv = summary.get("family_advantage", {})
    model_adv = summary.get("model_advantage", {})
    seed_adv = summary.get("seed_advantage", {})

    gates = [
        {"name": "effect_at_least_10pp", "passed": diff >= 0.10, "value": diff, "threshold": 0.10},
        {"name": "ci_excludes_zero", "passed": ci_low is not None and ci_low > 0, "value": ci_low, "threshold": ">0"},
        {"name": "wins_at_least_2_of_3_families", "passed": sum(v > 0 for v in family_adv.values()) >= 2, "value": family_adv},
        {"name": "beats_random_auditor", "passed": d_rate > e_rate, "value": d_rate - e_rate},
        {"name": "no_catastrophic_increase_2pp", "passed": catastrophic_delta < 0.02, "value": catastrophic_delta, "threshold": "<0.02"},
        {"name": "positive_equal_token_budget", "passed": equal_diff > 0, "value": equal_diff},
        {"name": "majority_models_positive", "passed": _majority_positive(model_adv), "value": model_adv},
        {"name": "majority_seeds_positive", "passed": _majority_positive(seed_adv), "value": seed_adv},
        {"name": "not_decisively_worse_than_checked_baseline", "passed": d_minus_b >= -0.10, "value": d_minus_b, "threshold": ">=-0.10"},
    ]
    if all(g["passed"] for g in gates):
        return {"verdict": "SUPPORTED", "reason": "All preregistered support gates passed.", "gates": gates}

    reproducibility_failed = not _majority_positive(model_adv) or not _majority_positive(seed_adv) or sum(v > 0 for v in family_adv.values()) <= 1
    refutation_reasons = []
    if diff <= 0 and ci_high is not None and ci_high < 0.05:
        refutation_reasons.append("95% CI rules out a +5pp meaningful advantage")
    if d_rate <= e_rate:
        refutation_reasons.append("semantic auditor does not beat random-auditor control")
    if catastrophic_delta >= 0.02:
        refutation_reasons.append("catastrophic false acceptance increased by at least 2pp")
    if equal_diff <= 0:
        refutation_reasons.append("advantage disappears under equal-token budget")
    if diff > 0 and reproducibility_failed:
        refutation_reasons.append("positive effect fails preregistered cross-family/model/seed reproducibility")
    if refutation_reasons:
        return {"verdict": "REFUTED", "reason": "; ".join(refutation_reasons), "gates": gates, "refutation_reasons": refutation_reasons}
    return {"verdict": "INCONCLUSIVE", "reason": "Evidence is neither strong enough for support nor decisive enough for refutation.", "gates": gates}


def decide_interim_stop(
    summary: dict[str, Any],
    config: Any,
    *,
    stage_number: int,
    completed_seed_count: int,
    confidence: float,
    primary_interval: dict[str, Any],
) -> dict[str, Any]:
    """Conservative optional-stopping gate for balanced cumulative seed stages.

    The full-sample 180-cluster verdict rule is untouched. Interim support uses
    a stricter confidence interval than the final 95% rule and additionally
    requires unanimous positive D-A direction across every observed model,
    family, and seed. Interim refutation is allowed only when the stricter
    interval rules out even the preregistered +5pp meaningful advantage.
    """
    if completed_seed_count >= len(config.seeds):
        return {"stop": False, "stage": stage_number, "reason": "final stage uses the original full-sample verdict rule"}
    if not (0.95 < float(confidence) < 1.0):
        raise ValueError("interim confidence must be stricter than 95% and below 100%")

    primary = summary.get("primary", {})
    diff = float(primary.get("d_minus_a") or 0.0)
    equal_diff = float(primary.get("equal_budget_diff") or 0.0)
    d_minus_b = float(primary.get("d_minus_b") or 0.0)
    lower = primary_interval.get("lower")
    upper = primary_interval.get("upper")
    d_rate = _metric(summary, "D_INVERTED", "success_rate")
    e_rate = _metric(summary, "E_RANDOM_AUDITOR", "success_rate")
    catastrophic_delta = _metric(summary, "D_INVERTED", "catastrophic_rate") - _metric(summary, "A_DIRECT", "catastrophic_rate")
    family_adv = summary.get("family_advantage", {})
    model_adv = summary.get("model_advantage", {})
    seed_adv = summary.get("seed_advantage", {})

    support_gates = [
        {"name": "interim_effect_at_least_10pp", "passed": diff >= 0.10, "value": diff, "threshold": 0.10},
        {"name": "interim_high_confidence_ci_excludes_zero", "passed": lower is not None and float(lower) > 0, "value": lower, "threshold": f">0 at {confidence:.3%} confidence"},
        {"name": "all_families_positive", "passed": _all_positive(family_adv), "value": family_adv},
        {"name": "beats_random_auditor", "passed": d_rate > e_rate, "value": d_rate - e_rate},
        {"name": "no_catastrophic_increase_2pp", "passed": catastrophic_delta < 0.02, "value": catastrophic_delta, "threshold": "<0.02"},
        {"name": "positive_equal_token_budget", "passed": equal_diff > 0, "value": equal_diff},
        {"name": "all_models_positive", "passed": _all_positive(model_adv), "value": model_adv},
        {"name": "all_observed_seeds_positive", "passed": _all_positive(seed_adv), "value": seed_adv},
        {"name": "not_decisively_worse_than_checked_baseline", "passed": d_minus_b >= -0.10, "value": d_minus_b, "threshold": ">=-0.10"},
    ]
    if all(g["passed"] for g in support_gates):
        return {
            "stop": True,
            "verdict": "SUPPORTED",
            "reason": f"Sequential early stop at stage {stage_number}: all support gates pass under a {confidence:.1%} primary interval with unanimous model/family/seed direction.",
            "gates": support_gates,
            "stage": stage_number,
            "completed_seed_count": completed_seed_count,
            "interim_confidence": confidence,
            "primary_interval": primary_interval,
        }

    # Early refutation is intentionally narrower than the full refutation rule:
    # only overwhelming primary evidence can stop early. Secondary failures
    # continue collecting data through the next stage/full sample.
    if diff <= 0 and upper is not None and float(upper) < 0.05:
        return {
            "stop": True,
            "verdict": "REFUTED",
            "reason": f"Sequential early stop at stage {stage_number}: the {confidence:.1%} primary interval rules out a +5pp meaningful D-A advantage.",
            "gates": support_gates,
            "refutation_reasons": [f"{confidence:.1%} interim CI rules out a +5pp meaningful advantage"],
            "stage": stage_number,
            "completed_seed_count": completed_seed_count,
            "interim_confidence": confidence,
            "primary_interval": primary_interval,
        }

    return {
        "stop": False,
        "verdict": "CONTINUE",
        "reason": "Interim evidence is not strong enough to lock the scientific conclusion; continue to the next balanced seed stage.",
        "gates": support_gates,
        "stage": stage_number,
        "completed_seed_count": completed_seed_count,
        "interim_confidence": confidence,
        "primary_interval": primary_interval,
    }
