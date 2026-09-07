from inverted_brain.contracts import MechanismCandidate, TrialResult
from inverted_brain.retention import decide_retention


def trial(i, passed, grammar="g", status="COMPLETE"):
    return TrialResult(str(i), "Q", status, passed, passed, metadata={"grammar":grammar})


def candidate(status="causally_supported", cost=0.0):
    return MechanismCandidate("m","when divergence","base","perform state reread",["e"],["state"],{"extra_steps":cost},status=status)


def test_retains_three_plus_lift_with_at_most_one_regression():
    base = [trial(i, i>=10, "a" if i%2 else "b") for i in range(24)]
    cand = [trial(i, i>=7, "a" if i%2 else "b") for i in range(24)]
    d = decide_retention(candidate(), base, cand)
    assert d.retained
    assert d.fresh_lift == 3


def test_rejects_regressions_and_missing_causal_support():
    base = [trial(i, True, "a") for i in range(24)]
    cand = [trial(i, i>1, "a") for i in range(24)]
    d = decide_retention(candidate(status="proposed"), base, cand)
    assert not d.retained
    assert "missing_causal_support" in d.reasons
    assert "regression_gate_failed" in d.reasons


def test_rejects_insufficient_holdout():
    d = decide_retention(candidate(), [trial(1,False)], [trial(1,True)])
    assert "insufficient_or_unpaired_holdout" in d.reasons
