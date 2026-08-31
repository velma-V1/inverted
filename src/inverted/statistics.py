from __future__ import annotations

from collections import Counter, defaultdict
import math
import random
import statistics as _stats
from typing import Any, Iterable

from .arms import TrialRecord


def _rate(num: int | float, den: int | float) -> float | None:
    return float(num) / float(den) if den else None


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(xs[lo])
    frac = pos - lo
    return float(xs[lo] * (1 - frac) + xs[hi] * frac)


def _dist(values: Iterable[float | None]) -> dict[str, float | None]:
    xs = [float(x) for x in values if x is not None]
    return {
        "n": len(xs),
        "mean": _stats.fmean(xs) if xs else None,
        "median": _stats.median(xs) if xs else None,
        "p50": _percentile(xs, 0.50),
        "p90": _percentile(xs, 0.90),
        "p95": _percentile(xs, 0.95),
        "p99": _percentile(xs, 0.99),
        "min": min(xs) if xs else None,
        "max": max(xs) if xs else None,
    }


def _arm_metrics(trials: list[TrialRecord]) -> dict[str, Any]:
    calls = [c for t in trials for c in t.model_calls]
    n = len(trials)
    successes = sum(t.success for t in trials)
    catastrophic = sum(t.catastrophic for t in trials)
    tp = sum(t.audit_tp for t in trials)
    tn = sum(t.audit_tn for t in trials)
    fp = sum(t.audit_fp for t in trials)
    fn = sum(t.audit_fn for t in trials)
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    specificity = _rate(tn, tn + fp)
    fpr = _rate(fp, fp + tn)
    fnr = _rate(fn, fn + tp)
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and (precision + recall) else None
    known_costs = [c.cost_usd for c in calls if c.cost_usd is not None]
    output_tokens = sum(c.output_tokens or 0 for c in calls)
    total_model_latency = sum(c.latency_s for c in calls)
    return {
        "n": n,
        "successes": successes,
        "success_rate": _rate(successes, n),
        "mean_requirement_accuracy": _stats.fmean([t.requirement_accuracy for t in trials]) if trials else None,
        "catastrophic_failures": catastrophic,
        "catastrophic_rate": _rate(catastrophic, n),
        "candidate_attempts": sum(t.candidate_attempts for t in trials),
        "rejections": sum(t.rejections for t in trials),
        "rejection_rate": _rate(sum(t.rejections for t in trials), sum(t.candidate_attempts for t in trials)),
        "budget_exhausted": sum(t.budget_exhausted for t in trials),
        "model_call_count": len(calls),
        "retry_call_count": sum(1 for c in calls if c.retry_number > 0),
        "timeout_count": sum(1 for c in calls if c.timeout),
        "parser_failure_count": sum(1 for c in calls if c.parse_success is False),
        "model_error_count": sum(1 for c in calls if c.error_class is not None),
        "input_tokens": sum(c.input_tokens or 0 for c in calls),
        "output_tokens": output_tokens,
        "reasoning_tokens": sum(c.reasoning_tokens or 0 for c in calls),
        "cached_tokens": sum(c.cached_tokens or 0 for c in calls),
        "cache_write_tokens": sum(c.cache_write_tokens or 0 for c in calls),
        "total_tokens": sum(c.total_tokens or 0 for c in calls),
        "tokens_per_success": _rate(sum(c.total_tokens or 0 for c in calls), successes),
        "known_cost_usd": sum(known_costs) if known_costs else None,
        "known_cost_per_success_usd": _rate(sum(known_costs), successes) if known_costs else None,
        "latency_s": _dist([t.end_to_end_latency_s for t in trials]),
        "model_call_latency_s": _dist([c.latency_s for c in calls]),
        "ttft_s": _dist([c.ttft_s for c in calls]),
        "generated_tokens_per_s": _dist([c.generated_tokens_per_s for c in calls]),
        "end_to_end_tokens_per_s": _dist([c.end_to_end_tokens_per_s for c in calls]),
        "aggregate_output_tokens_per_model_second": _rate(output_tokens, total_model_latency),
        "auditor": {
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "specificity": specificity,
            "f1": f1, "false_positive_rate": fpr, "false_negative_rate": fnr,
        },
        "failure_taxonomy": dict(Counter(r for t in trials for r in t.failure_reasons)),
        "terminal_status": dict(Counter(t.terminal_status for t in trials)),
    }


def _baseline_key(t: TrialRecord) -> tuple[Any, ...]:
    """Condition identity for quality-independent direct baselines."""
    return (t.task_id, t.family, t.complexity, t.model, t.seed, t.epoch)


def _collapsed_baseline_success(trials: list[TrialRecord], arm: str) -> dict[tuple[Any, ...], float]:
    grouped: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for t in trials:
        if t.arm == arm:
            grouped[_baseline_key(t)].append(float(int(t.success)))
    return {key: _stats.fmean(values) for key, values in grouped.items()}


def bootstrap_rate_difference(trials: list[TrialRecord], treatment_arm: str, baseline_arm: str, samples: int = 2000, seed: int = 20260830) -> dict[str, float | int | None]:
    baseline = _collapsed_baseline_success(trials, baseline_arm)
    paired: list[tuple[TrialRecord, float]] = []
    for treatment in trials:
        if treatment.arm != treatment_arm:
            continue
        baseline_success = baseline.get(_baseline_key(treatment))
        if baseline_success is not None:
            paired.append((treatment, float(int(treatment.success)) - baseline_success))

    if not paired:
        return {"estimate": None, "lower": None, "upper": None, "n_pairs": 0, "n_clusters": 0, "samples": samples}

    # A/B are quality-independent and may now be physically executed only once.
    # Each D quality row is paired to that deduplicated baseline analytically.
    # Repeated model/quality effects are then collapsed within task_id before
    # bootstrap resampling so they cannot manufacture independent sample size.
    by_task: dict[str, list[float]] = defaultdict(list)
    for treatment, diff in paired:
        by_task[treatment.task_id].append(diff)
    cluster_effects = [_stats.fmean(values) for _, values in sorted(by_task.items())]
    estimate = _stats.fmean(cluster_effects)
    rng = random.Random(seed)
    boots: list[float] = []
    n_clusters = len(cluster_effects)
    for _ in range(samples):
        boots.append(_stats.fmean(cluster_effects[rng.randrange(n_clusters)] for _ in range(n_clusters)))
    return {
        "estimate": estimate,
        "lower": _percentile(boots, 0.025),
        "upper": _percentile(boots, 0.975),
        "n_pairs": len(paired),
        "n_clusters": n_clusters,
        "samples": samples,
    }


def _advantage_by(trials: list[TrialRecord], attribute: str) -> dict[str, float]:
    groups: dict[Any, list[TrialRecord]] = defaultdict(list)
    for t in trials:
        groups[getattr(t, attribute)].append(t)
    out: dict[str, float] = {}
    for key, group in groups.items():
        d = [int(t.success) for t in group if t.arm == "D_INVERTED"]
        a = [int(t.success) for t in group if t.arm == "A_DIRECT"]
        if d and a:
            out[str(key)] = _stats.fmean(d) - _stats.fmean(a)
    return out


def _baseline_rate(trials: list[TrialRecord], arm: str) -> float | None:
    collapsed = _collapsed_baseline_success(trials, arm)
    return _stats.fmean(collapsed.values()) if collapsed else None


def estimate_crossover(trials: list[TrialRecord]) -> dict[str, Any]:
    by_q: dict[float, list[int]] = defaultdict(list)
    for t in trials:
        if t.arm == "D_INVERTED":
            by_q[t.configured_executor_quality].append(int(t.success))

    a = _baseline_rate(trials, "A_DIRECT")
    b = _baseline_rate(trials, "B_DIRECT_CHECKED")
    points = []
    crossover = None
    for quality in sorted(by_q):
        d = _stats.fmean(by_q[quality]) if by_q[quality] else None
        da = d - a if d is not None and a is not None else None
        db = d - b if d is not None and b is not None else None
        points.append({"quality": quality, "a_success": a, "b_success": b, "d_success": d, "d_minus_a": da, "d_minus_b": db})
        if crossover is None and da is not None and da > 0:
            crossover = quality
    return {"crossover_quality": crossover, "points": points}


def _slice_metrics(trials: list[TrialRecord], attribute: str) -> dict[str, Any]:
    groups: dict[str, list[TrialRecord]] = defaultdict(list)
    for t in trials:
        groups[str(getattr(t, attribute))].append(t)
    return {k: _arm_metrics(v) for k, v in sorted(groups.items())}


def aggregate_trials(trials: list[TrialRecord], bootstrap_samples: int = 2000, bootstrap_seed: int = 20260830) -> dict[str, Any]:
    by_arm_groups: dict[str, list[TrialRecord]] = defaultdict(list)
    for t in trials:
        by_arm_groups[t.arm].append(t)
    by_arm = {arm: _arm_metrics(group) for arm, group in sorted(by_arm_groups.items())}
    ci = bootstrap_rate_difference(trials, "D_INVERTED", "A_DIRECT", bootstrap_samples, bootstrap_seed)
    d_rate = by_arm.get("D_INVERTED", {}).get("success_rate")
    a_rate = _baseline_rate(trials, "A_DIRECT")
    b_rate = _baseline_rate(trials, "B_DIRECT_CHECKED")
    primary_diff = (d_rate - a_rate) if d_rate is not None and a_rate is not None else None
    d_minus_b = (d_rate - b_rate) if d_rate is not None and b_rate is not None else None
    failures = Counter(r for t in trials for r in t.failure_reasons)
    return {
        "n_trials": len(trials),
        "by_arm": by_arm,
        "primary": {
            "d_minus_a": primary_diff,
            "ci95": ci,
            # Every model-using arm is hard-capped by the same configured token budget.
            "equal_budget_diff": primary_diff,
            "d_minus_b": d_minus_b,
            "independent_task_clusters": ci.get("n_clusters", 0),
        },
        "family_advantage": _advantage_by(trials, "family"),
        "model_advantage": _advantage_by(trials, "model"),
        "seed_advantage": _advantage_by(trials, "seed"),
        "complexity_advantage": _advantage_by(trials, "complexity"),
        "quality_crossover": estimate_crossover(trials),
        "failure_taxonomy": dict(failures),
        "slices": {
            "model": _slice_metrics(trials, "model"),
            "family": _slice_metrics(trials, "family"),
            "complexity": _slice_metrics(trials, "complexity"),
            "quality": _slice_metrics(trials, "configured_executor_quality"),
            "seed": _slice_metrics(trials, "seed"),
            "epoch": _slice_metrics(trials, "epoch"),
        },
    }
