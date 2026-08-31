from __future__ import annotations

import math
import random
from typing import Any


PREREGISTRATION: dict[str, Any] = {
    "experiment": "VELMA Inverted Test 2 — bounded local causal specialization/repair campaign",
    "builds_on": "Test 1 refuted universal inversion and exposed validator/retry/auditor confounds; the model-free Test-2 atlas is Tier C hypothesis generation only.",
    "evidence_tier": "A",
    "primary_hypothesis": {
        "statement": "On matched deterministic failures, structured-feedback targeted repair increases hidden-gold recovery by at least 10 percentage points over equal-budget raw-feedback full regeneration, exceeds the preregistered 34.31% third-blind-retry break-even, and does not increase catastrophic failures by 2 percentage points or more.",
        "treatment": "structured feedback + targeted repair",
        "control": "raw failure IDs + full regeneration",
        "minimum_effect_pp": 10.0,
        "third_retry_break_even": 0.3431,
        "confidence_level": 0.95,
        "matched_factorial_cells_per_condition": 18,
        "equal_budget": "18 physical calls per primary condition: same 3 selected repair models × same 6 fixed failing candidates; one call per model/candidate/condition.",
    },
    "success_gates": {
        "all_required": True,
        "structured_targeted_wilson_lower_gt": 0.3431,
        "paired_effect_point_estimate_pp_gte": 10.0,
        "paired_effect_bootstrap_ci95_lower_gt_pp": 0.0,
        "catastrophic_increase_pp_lt": 2.0,
        "complete_matched_primary_cells": True,
    },
    "failure_gates": {
        "catastrophic_increase_pp": 2.0,
        "structured_targeted_wilson_upper_lte": 0.3431,
        "paired_effect_bootstrap_ci95_upper_lte_pp": 0.0,
    },
    "stopping_rule": "FIXED_BUDGET_NO_SEQUENTIAL_EARLY_STOP",
    "hard_physical_call_ceiling": 480,
    "phase_budgets": {
        "formalization": 60,
        "execution": 60,
        "auditing": 100,
        "atomic_audit": 20,
        "repair_factorial": 100,
        "progressive_holdout": 100,
        "stability": 40,
        "reserve": 0,
    },
    "secondary_estimands": [
        "model × role × family × complexity × representation capability with confidence intervals",
        "holistic versus atomic auditor false-accept and false-reject behavior on matched decision-sensitive cases",
        "repair feedback main effect, repair strategy main effect, and feedback×strategy interaction",
        "S0→S4 progressive specialization wins created/destroyed on four untouched hard holdouts",
        "alternate audit-before-repair ordering versus repair-before-audit",
        "model complementarity, unique wins, disagreement risk, router regret, and oracle routing headroom",
        "tokens, wall latency, load latency, prompt-eval latency, eval latency, and physical calls per recovered win",
    ],
    "architecture_claim_guardrail": "The four-task progressive holdout is diagnostic Tier-A evidence but is not powered to support a universal layered-architecture claim. Any global architecture verdict from that block alone is INCONCLUSIVE; it is used to preregister the next confirmatory campaign.",
    "evidence_contract": [
        "events.jsonl",
        "model_calls.jsonl",
        "trials.csv",
        "trials.jsonl",
        "failures.csv",
        "summary.json",
        "summary.csv",
        "report.txt",
        "config.json",
        "provenance.json",
        "preregistration.json",
        "verdict.json",
        "SHA256SUMS.csv",
        "TEST2-NEXT-STRIDE-REPORT.txt",
        "TEST2-COMPLETE-EVIDENCE.txt",
    ],
    "if_supported_next": "Confirm the winning repair mechanism inside a larger matched progressive architecture campaign, preserving mutation-boundary deterministic validation and testing whether repair gains survive role-specialized routing.",
    "if_refuted_next": "Do not prompt-tune the failed repair arm. Use the recorded failure taxonomy to test the highest residual causal mechanism: alternate repair model, fault-specific routing, or additional fresh candidate generation depending on measured break-even headroom.",
    "if_inconclusive_next": "Increase only the matched primary repair sample required to narrow the confidence interval; preserve models, prompts, conditions, scoring, and gates.",
    "change_my_mind": "A future preregistered Tier-A replication with the same causal contrast and adequate power whose confidence interval reverses the current conclusion, without a >=2pp catastrophic-rate increase.",
}


def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / n) + z2 / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _paired_bootstrap_ci(differences: list[int], *, iterations: int = 20000, seed: int = 20260831) -> tuple[float, float]:
    if not differences:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(differences)
    samples: list[float] = []
    for _ in range(iterations):
        total = sum(differences[rng.randrange(n)] for _ in range(n))
        samples.append(total / n)
    return (_percentile(samples, 0.025), _percentile(samples, 0.975))


def _cell(rows: list[dict[str, Any]], feedback_style: str, strategy: str) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("feedback_style") == feedback_style and r.get("strategy") == strategy]


def evaluate_primary_verdict(repair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    treatment = _cell(repair_rows, "structured", "targeted")
    control = _cell(repair_rows, "raw", "regenerate")
    expected_n = int(PREREGISTRATION["primary_hypothesis"]["matched_factorial_cells_per_condition"])
    t_by_key = {(str(r.get("model")), str(r.get("task_id"))): r for r in treatment}
    c_by_key = {(str(r.get("model")), str(r.get("task_id"))): r for r in control}
    complete = len(treatment) == expected_n and len(control) == expected_n and len(t_by_key) == expected_n and set(t_by_key) == set(c_by_key)
    if not complete:
        return {
            "verdict": "NON-DECISIVE",
            "reason": "Primary matched factorial evidence contract incomplete.",
            "expected_per_condition": expected_n,
            "treatment_rows": len(treatment),
            "control_rows": len(control),
            "matched_keys": len(set(t_by_key) & set(c_by_key)),
            "success_reasons": [],
            "failure_reasons": [],
        }

    t_success = sum(bool(r.get("success")) for r in treatment)
    c_success = sum(bool(r.get("success")) for r in control)
    t_low, t_high = _wilson(t_success, expected_n)
    c_low, c_high = _wilson(c_success, expected_n)
    differences = [int(bool(t_by_key[k].get("success"))) - int(bool(c_by_key[k].get("success"))) for k in sorted(t_by_key)]
    paired_effect = sum(differences) / expected_n
    effect_low, effect_high = _paired_bootstrap_ci(differences)

    t_cat = sum(bool(r.get("catastrophic")) for r in treatment)
    c_cat = sum(bool(r.get("catastrophic")) for r in control)
    catastrophic_delta = (t_cat - c_cat) / expected_n
    break_even = float(PREREGISTRATION["primary_hypothesis"]["third_retry_break_even"])
    min_effect_pp = float(PREREGISTRATION["primary_hypothesis"]["minimum_effect_pp"])

    success_reasons: list[str] = []
    failure_reasons: list[str] = []
    success_checks = {
        "recovery_ci_clears_third_retry_break_even": t_low > break_even,
        "paired_effect_point_estimate": paired_effect * 100.0 >= min_effect_pp,
        "paired_effect_ci_positive": effect_low * 100.0 > 0.0,
        "catastrophic_delta_below_failure_gate": catastrophic_delta * 100.0 < 2.0,
    }
    for name, passed in success_checks.items():
        if passed:
            success_reasons.append(name)

    failure_checks = {
        "catastrophic increase reached >=2pp failure gate": catastrophic_delta * 100.0 >= 2.0,
        "structured targeted repair 95% upper CI is <= third-retry break-even": t_high <= break_even,
        "paired effect 95% upper CI is <=0pp": effect_high * 100.0 <= 0.0,
    }
    for reason, failed in failure_checks.items():
        if failed:
            failure_reasons.append(reason)

    if failure_reasons:
        verdict = "REFUTED"
    elif all(success_checks.values()):
        verdict = "SUPPORTED"
    else:
        verdict = "INCONCLUSIVE"

    return {
        "verdict": verdict,
        "hypothesis": PREREGISTRATION["primary_hypothesis"]["statement"],
        "n_matched": expected_n,
        "structured_targeted": {
            "successes": t_success,
            "n": expected_n,
            "rate": t_success / expected_n,
            "ci95_low": t_low,
            "ci95_high": t_high,
            "catastrophic": t_cat,
            "catastrophic_rate": t_cat / expected_n,
        },
        "raw_regenerate": {
            "successes": c_success,
            "n": expected_n,
            "rate": c_success / expected_n,
            "ci95_low": c_low,
            "ci95_high": c_high,
            "catastrophic": c_cat,
            "catastrophic_rate": c_cat / expected_n,
        },
        "paired_effect_pp": paired_effect * 100.0,
        "paired_effect_ci95_low_pp": effect_low * 100.0,
        "paired_effect_ci95_high_pp": effect_high * 100.0,
        "catastrophic_delta_pp": catastrophic_delta * 100.0,
        "third_retry_break_even": break_even,
        "minimum_effect_pp": min_effect_pp,
        "success_checks": success_checks,
        "success_reasons": success_reasons,
        "failure_checks": failure_checks,
        "failure_reasons": failure_reasons,
        "bootstrap_iterations": 20000,
        "bootstrap_seed": 20260831,
    }
