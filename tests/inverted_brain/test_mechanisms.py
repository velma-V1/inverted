from inverted_brain.contracts import CriticalDivergence, ReplayResult, MechanismCandidate
from inverted_brain.mechanisms import extract_candidate, validate_candidate


def test_candidate_requires_necessity_and_sufficiency_evidence():
    d = CriticalDivergence("t",1,1,"qwen_mutation_instead_of_state_reread",["q1","c1"],"state_reread",0.8)
    removed = ReplayResult("t-remove",2,0,2,0.0,["rm0","rm1"])
    forced = ReplayResult("t-force",2,2,0,1.0,["f0","f1"])
    c = extract_candidate(d,[removed,forced])
    assert c.status == "causally_supported"
    assert c.replacement_behavior == "state_reread"
    assert set(["q1","c1","rm0","f0"]).issubset(c.evidence_ids)
    assert validate_candidate(c) == []


def test_candidate_stays_proposed_without_both_causal_directions():
    d = CriticalDivergence("t",1,1,"x",["e"],"verification",0.7)
    only_force = ReplayResult("t-force",2,2,0,1.0,["f"])
    assert extract_candidate(d,[only_force]).status == "proposed"


def test_candidate_rejects_benchmark_encoding_and_teacher_dump():
    c = MechanismCandidate("m","when brain2-task","base","ANS_deadbeef\ntrajectory\nline2\nline3\nline4\nline5",["e"],["x"])
    problems = validate_candidate(c)
    assert "benchmark_encoding" in problems
    assert "teacher_trajectory_copy" in problems
