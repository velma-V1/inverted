from inverted.harvest_d.statistics import anytime_hoeffding_cs, sequential_evidence
from inverted.harvest_d.types import SequentialDecision


def test_anytime_sequence_contains_observed_mean_and_shrinks_with_n():
    small = anytime_hoeffding_cs([1, 0, 1, 1], alpha=0.01)
    large = anytime_hoeffding_cs([1, 0, 1, 1] * 16, alpha=0.01)
    assert small.lower <= 0.75 <= small.upper
    assert large.lower <= 0.75 <= large.upper
    assert (large.upper - large.lower) < (small.upper - small.lower)
    assert large.method.startswith("ANYTIME_HOEFFDING")


def test_anytime_sequence_supports_matched_deltas_in_minus_one_to_one():
    cs = anytime_hoeffding_cs([1, 0, -1, 1] * 16, alpha=0.05)
    assert cs.lower <= 0.25 <= cs.upper
    assert cs.bounds == (-1.0, 1.0)


def test_hard_violation_overrides_positive_effect():
    evidence = sequential_evidence([1] * 64, margin=0.02, hard_violation=True)
    assert evidence.decision is SequentialDecision.HARMFUL


def test_empty_sequence_is_unresolved_not_fake_precision():
    evidence = sequential_evidence([], margin=0.02)
    assert evidence.decision is SequentialDecision.UNRESOLVED
    assert evidence.interval.n == 0
