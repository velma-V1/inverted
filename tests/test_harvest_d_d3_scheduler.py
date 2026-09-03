from inverted.harvest_d.d3_scheduler import D3Scheduler, ExperimentCandidate
from inverted.harvest_d.types import SequentialDecision


def _candidate(candidate_id: str, **kwargs) -> ExperimentCandidate:
    return ExperimentCandidate(candidate_id=candidate_id, mechanism_id=kwargs.pop("mechanism_id", candidate_id), **kwargs)


def test_scheduler_prioritizes_hard_invariant_uncertainty_first():
    candidates = [
        _candidate("semantic", semantic_uncertainty=1.0),
        _candidate("safety", hard_invariant_uncertainty=0.1),
        _candidate("recovery", recovery_uncertainty=1.0),
    ]
    chosen = D3Scheduler.default(random_stream_fraction=0.0).select_next(candidates)
    assert chosen.candidate_id == "safety"
    assert chosen.priority_reason == "HARD_INVARIANT_UNCERTAINTY"
    assert chosen.selection_mode == "ADAPTIVE"


def test_harmful_candidate_only_receives_contradiction_check():
    scheduler = D3Scheduler.default()
    scheduler.observe("m1", SequentialDecision.HARMFUL)
    remaining = scheduler.remaining_for("m1")
    assert remaining
    assert all(item.kind == "CONTRADICTION_CHECK" for item in remaining)


def test_scheduler_preserves_protected_random_exploration_stream():
    scheduler = D3Scheduler.default(random_stream_fraction=0.10, seed=20260903)
    candidates = [_candidate(f"c{i}", semantic_uncertainty=0.5) for i in range(5)]
    picks = [scheduler.select_next(candidates) for _ in range(100)]
    random_picks = [p for p in picks if p.selection_mode == "PROTECTED_RANDOM"]
    assert 8 <= len(random_picks) <= 12
    assert all(p.selection_probability > 0 for p in random_picks)


def test_sealed_candidates_are_not_selectable_before_sealed_phase():
    scheduler = D3Scheduler.default(random_stream_fraction=0.0)
    candidates = [
        _candidate("dev", semantic_uncertainty=0.1),
        _candidate("sealed", hard_invariant_uncertainty=1.0, sealed=True),
    ]
    chosen = scheduler.select_next(candidates)
    assert chosen.candidate_id == "dev"


def test_scheduler_decision_preserves_alternative_scores():
    scheduler = D3Scheduler.default(random_stream_fraction=0.0)
    chosen = scheduler.select_next([
        _candidate("a", semantic_uncertainty=0.8),
        _candidate("b", semantic_uncertainty=0.7),
    ])
    assert {row["candidate_id"] for row in chosen.alternatives} == {"a", "b"}
