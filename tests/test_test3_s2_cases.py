from collections import Counter, defaultdict

from inverted.oracle import evaluate_task
from inverted.test3_s2_cases import build_holdout_b, build_seed_failure_s2


def test_holdout_b_is_fresh_balanced_72_case_causal_twin_set():
    cases = build_holdout_b()
    assert len(cases) == 72
    assert len({case.case_id for case in cases}) == 72
    assert all(case.case_id.startswith("test3-s2-BR1-") for case in cases)
    assert not any("test3-s1-" in case.case_id for case in cases)

    dimensions = Counter((case.task.family, case.task.complexity, case.metadata["perturbation_class"]) for case in cases)
    assert len(dimensions) == 6 * 4 * 3
    assert set(dimensions.values()) == {1}

    twins = defaultdict(set)
    for case in cases:
        twins[case.metadata["base_task_id"]].add(case.metadata["perturbation_class"])
    assert len(twins) == 24
    assert all(kinds == {"localized", "compound", "structural"} for kinds in twins.values())


def test_every_s2_seed_fixture_is_verified_failure_and_public_metadata_excludes_fault_label():
    for case in build_holdout_b():
        candidate = build_seed_failure_s2(case)
        result = evaluate_task(case.task, candidate.state, candidate.actions)
        assert result.success is False
        assert case.metadata["perturbation_class"] not in str(candidate.metadata.get("public_evidence", ""))
        public = dict(candidate.metadata.get("public_evidence") or {})
        forbidden = {"perturbation_class", "fault_type", "injected_faults", "target_state", "hidden_gold"}
        assert forbidden.isdisjoint(public)
