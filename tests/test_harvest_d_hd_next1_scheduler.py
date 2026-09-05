from __future__ import annotations

from inverted.harvest_d.hd_next1_scheduler import Candidate, HDNext1Scheduler, qwen_call_is_decision_relevant
from inverted.harvest_d.types import SequentialDecision


def _candidate(i: int, model: str = "SMALL_A") -> Candidate:
    return Candidate(
        candidate_id=f"c{i}",
        mechanism_id=f"m{i}",
        model_key=model,
        decision_id="D-SUPPORT",
        decision_change_reason="can change architecture",
        architecture_changing_uncertainty=1.0,
        uncovered_high_value_interaction=float(i % 2),
    )


def test_scheduler_preserves_at_least_ten_percent_random_challenger_stream():
    scheduler = HDNext1Scheduler(seed=9, protected_random_fraction=0.10)
    picks = scheduler.plan_block([_candidate(i) for i in range(100)], block_size=100)
    assert sum(row.protected_random for row in picks) >= 10


def test_harmful_and_futile_candidates_stop_ordinary_spending():
    scheduler = HDNext1Scheduler(seed=9)
    scheduler.observe("x", SequentialDecision.HARMFUL)
    scheduler.observe("y", SequentialDecision.FUTILE)
    assert scheduler.allowed_kinds("x") == ("CONTRADICTION_CHECK",)
    assert scheduler.allowed_kinds("y") == ()


def test_qwen_call_requires_named_decision_change_reason():
    bad = Candidate("x", "m", "QWEN", "D-MODEL", "")
    good = Candidate("y", "m", "QWEN", "D-MODEL", "can change ownership")
    assert qwen_call_is_decision_relevant(bad) is False
    assert qwen_call_is_decision_relevant(good) is True
