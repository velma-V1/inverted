from __future__ import annotations

from .contracts import MechanismCandidate, RetentionDecision, TrialResult
from .mechanisms import validate_candidate


def _clean_pass(trial: TrialResult) -> bool:
    return trial.status == "COMPLETE" and trial.outcome_passed and trial.process_passed


def decide_retention(
    candidate: MechanismCandidate,
    baseline_trials: list[TrialResult],
    candidate_trials: list[TrialResult],
    min_fresh_lift: int = 3,
    max_regressions: int = 1,
) -> RetentionDecision:
    reasons: list[str] = []
    if candidate.status not in {"causally_supported", "dev_passed"}:
        reasons.append("missing_causal_support")
    reasons.extend(validate_candidate(candidate))
    if len(baseline_trials) != len(candidate_trials) or len(candidate_trials) < 24:
        reasons.append("insufficient_or_unpaired_holdout")

    paired = list(zip(baseline_trials, candidate_trials))
    lift = sum(1 for b, c in paired if not _clean_pass(b) and _clean_pass(c))
    regressions = sum(1 for b, c in paired if _clean_pass(b) and not _clean_pass(c))
    catastrophic = any(c.status in {"INVALID_EVIDENCE", "ABORTED_INFRASTRUCTURE"} and b.status == "COMPLETE" for b, c in paired)
    if lift < min_fresh_lift:
        reasons.append("fresh_lift_below_gate")
    if regressions > max_regressions:
        reasons.append("regression_gate_failed")
    if catastrophic:
        reasons.append("catastrophic_new_failure")
    grammars = {str(c.metadata.get("grammar")) for _, c in paired if _clean_pass(c)}
    bounded_scope = None
    if len(grammars - {"None"}) < 2:
        if candidate.scope:
            bounded_scope = candidate.scope[0]
        else:
            reasons.append("no_cross_grammar_or_bounded_scope")
    extra_steps = float(candidate.cost.get("extra_steps", 0.0))
    if extra_steps > max(1.0, float(lift)):
        reasons.append("complexity_rent_failed")
    return RetentionDecision(not reasons, reasons, lift, regressions, bounded_scope)
