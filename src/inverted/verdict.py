from __future__ import annotations

from typing import Any


def _metric(summary: dict[str, Any], arm: str, name: str, default: float = 0.0) -> float:
    value = summary.get("by_arm", {}).get(arm, {}).get(name)
    return default if value is None else float(value)


def _majority_positive(values: dict[str, float]) -> bool:
    if not values:
        return False
    return sum(v > 0 for v in values.values()) > len(values) / 2


def decide_verdict(summary: dict[str, Any], config: Any) -> dict[str, Any]:
    a_n = int(summary.get("by_arm", {}).get("A_DIRECT", {}).get("n", 0))
    d_n = int(summary.get("by_arm", {}).get("D_INVERTED", {}).get("n", 0))
    minimum = int(config.minimum_primary_trials)
    if not bool(config.decisive) or min(a_n, d_n) < minimum:
        return {
            "verdict": "NON-DECISIVE",
            "reason": "Run is smoke/non-decisive or lacks preregistered minimum primary observations.",
            "observations": {"A_DIRECT": a_n, "D_INVERTED": d_n, "minimum_each": minimum},
            "gates": [],
        }

    primary = summary["primary"]
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
