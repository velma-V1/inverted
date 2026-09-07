from inverted.universal_tuning.statistics import (
    PairedBatch,
    classify_comparison,
    paired_bootstrap_ci,
    required_checkpoint,
)


def batches(base_pattern, candidate_pattern, count=8):
    return tuple(
        PairedBatch(
            batch_id=f"b{i}",
            baseline=tuple(base_pattern),
            candidate=tuple(candidate_pattern),
        )
        for i in range(count)
    )


def test_clustered_bootstrap_is_deterministic():
    data = batches([1, 1, 1, 0, 0], [1, 1, 1, 1, 0], 12)
    a = paired_bootstrap_ci(data, seed=77, iterations=1000)
    b = paired_bootstrap_ci(data, seed=77, iterations=1000)
    assert a == b
    assert a.n_atomic == 60
    assert round(a.delta, 3) == 0.2


def test_superiority_requires_forty_and_five_point_lower_bound():
    data = batches([1, 1, 1, 1, 0], [1, 1, 1, 1, 1], 8)
    cmp = paired_bootstrap_ci(data, seed=1, iterations=500)
    assert cmp.n_atomic == 40
    assert classify_comparison(cmp) == "SUPERIOR"


def test_cannot_certify_before_forty_atomic_tasks():
    data = batches([1, 1, 1, 1, 0], [1, 1, 1, 1, 1], 7)
    cmp = paired_bootstrap_ci(data, seed=1, iterations=300)
    assert cmp.n_atomic == 35
    assert classify_comparison(cmp) == "INSUFFICIENT"
    assert required_checkpoint(cmp) == 40


def test_equivalence_band_returns_plateau_not_fake_winner():
    data = batches([1, 1, 1, 1, 0], [1, 1, 1, 1, 0], 8)
    cmp = paired_bootstrap_ci(data, seed=2, iterations=500)
    assert cmp.ci_low == 0.0 and cmp.ci_high == 0.0
    assert classify_comparison(cmp) == "EQUIVALENT"
    assert required_checkpoint(cmp) == 40


def test_uncertain_close_comparison_expands_checkpoints():
    patterns = (
        PairedBatch("a", (1,1,1,1,0), (1,1,1,1,1)),
        PairedBatch("b", (1,1,1,1,1), (1,1,1,1,0)),
    )
    data = patterns * 4
    cmp40 = paired_bootstrap_ci(data, seed=3, iterations=1000)
    assert cmp40.n_atomic == 40
    assert classify_comparison(cmp40) == "CLOSE"
    assert required_checkpoint(cmp40) == 60
    cmp60 = paired_bootstrap_ci(patterns * 6, seed=3, iterations=1000)
    assert required_checkpoint(cmp60) == 80
    cmp80 = paired_bootstrap_ci(patterns * 8, seed=3, iterations=1000)
    assert required_checkpoint(cmp80) == 120


def test_unresolved_close_at_120_becomes_tie_or_plateau():
    patterns = (
        PairedBatch("a", (1,1,1,1,0), (1,1,1,1,1)),
        PairedBatch("b", (1,1,1,1,1), (1,1,1,1,0)),
    )
    cmp = paired_bootstrap_ci(patterns * 12, seed=5, iterations=1000)
    assert cmp.n_atomic == 120
    assert classify_comparison(cmp) == "TIE_OR_PLATEAU"
    assert required_checkpoint(cmp) == 120
