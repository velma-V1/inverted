from types import SimpleNamespace
from inverted_brain.contracts import DifficultyVector
from inverted_brain.frontier import FrontierSampler


def task(grammar, level):
    return SimpleNamespace(grammar=grammar, difficulty=DifficultyVector(constraints=level))


def test_mixed_stratum_scores_above_all_pass_or_all_fail():
    sampler = FrontierSampler(seed=7)
    mixed = task("a", 1); passed = task("b", 1); failed = task("c", 1)
    for value in [True, False, True, False]: sampler.observe(mixed, value)
    for _ in range(4): sampler.observe(passed, True)
    for _ in range(4): sampler.observe(failed, False)
    assert sampler.score(mixed) > sampler.score(passed)
    assert sampler.score(mixed) > sampler.score(failed)
    assert sampler.score(passed) > 0


def test_selection_preserves_grammar_diversity():
    sampler = FrontierSampler(seed=1)
    pool = [task("a", 1), task("a", 2), task("b", 1), task("c", 1)]
    selected = sampler.next_batch(pool, 3)
    assert len({x.grammar for x in selected}) == 3


def test_seed_replay_is_deterministic():
    pool = [task("a", i) for i in range(1, 6)]
    a = FrontierSampler(seed=22).next_batch(pool, 3)
    b = FrontierSampler(seed=22).next_batch(pool, 3)
    assert [x.difficulty.key() for x in a] == [x.difficulty.key() for x in b]
