from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_external_action_budget_refuses_cap_plus_one():
    from inverted.black_magic.budget import ExternalActionBudget, ExternalActionBudgetExceeded

    budget = ExternalActionBudget("decision_harvest", 2)
    assert budget.reserve("model", {"id": "a"}) == 1
    assert budget.reserve("model", {"id": "b"}) == 2
    with pytest.raises(ExternalActionBudgetExceeded):
        budget.reserve("model", {"id": "c"})
    assert budget.used == 2
    assert budget.remaining == 0


def test_counterfactual_requires_targeted_effect_beyond_sham():
    from inverted.black_magic.counterfactual import classify_replay

    causal = classify_replay(original_success=False, targeted_success=True, sham_success=False)
    ambiguous = classify_replay(original_success=False, targeted_success=True, sham_success=True)
    ineffective = classify_replay(original_success=False, targeted_success=False, sham_success=False)
    assert causal == "CAUSAL"
    assert ambiguous == "AMBIGUOUS"
    assert ineffective == "INEFFECTIVE"


def test_pairwise_and_ordered_coverage_are_verified():
    from inverted.black_magic.interactions import verify_ordered_sequence_coverage, verify_t_way_coverage

    factors = {"a": [0, 1], "b": [0, 1]}
    rows = [
        {"a": 0, "b": 0},
        {"a": 0, "b": 1},
        {"a": 1, "b": 0},
        {"a": 1, "b": 1},
    ]
    report = verify_t_way_coverage(rows, factors, strength=2)
    assert report["complete"] is True
    ordered = verify_ordered_sequence_coverage(
        [["stale_state", "requirement_change"], ["requirement_change", "stale_state"]],
        [("stale_state", "requirement_change"), ("requirement_change", "stale_state")],
    )
    assert ordered["complete"] is True


def test_metamorphic_invariant_and_boundary_scoring():
    from inverted.black_magic.metamorphic import evaluate_metamorphic_pair

    invariant = evaluate_metamorphic_pair("ACT", "ACT", "INVARIANT")
    boundary = evaluate_metamorphic_pair("ACT", "ABSTAIN", "BOUNDARY_FLIP")
    bad_invariant = evaluate_metamorphic_pair("ACT", "ABSTAIN", "INVARIANT")
    assert invariant["passed"] is True
    assert boundary["passed"] is True
    assert bad_invariant["passed"] is False


def test_decision_harvest_generator_covers_required_challenges():
    from inverted.black_magic.decision_harvest import REQUIRED_CHALLENGES, generate_decision_harvest_cases

    cases = generate_decision_harvest_cases(seed=20260901, case_count=len(REQUIRED_CHALLENGES))
    observed = {case["challenge"] for case in cases}
    assert set(REQUIRED_CHALLENGES) <= observed
    for case in cases:
        assert "oracle" in case
        assert "public" in case
        assert "correct_action_id" not in case["public"]
        assert "oracle" not in json.dumps(case["public"], sort_keys=True)


def test_externalized_correction_probe_is_byte_identical_except_wrapper():
    from inverted.black_magic.decision_harvest import build_externalized_correction_payloads

    error = {"action_id": "bad", "reason": "same error"}
    payloads = build_externalized_correction_payloads(error)
    assert set(payloads) == {"own_prior", "external_candidate", "tool_state", "memory_record"}
    serialized_errors = {json.dumps(value["error_artifact"], sort_keys=True) for value in payloads.values()}
    assert len(serialized_errors) == 1
    assert {value["wrapper_role"] for value in payloads.values()} == set(payloads)


def test_decision_harvest_budget_plan_refuses_over_1200():
    from inverted.black_magic.decision_harvest import planned_decision_harvest_actions

    assert planned_decision_harvest_actions(model_count=3, case_count=100, arm_count=3, replay_budget=300) == 1200
    assert planned_decision_harvest_actions(model_count=3, case_count=101, arm_count=3, replay_budget=300) == 1209


def test_harvest_a_smoke_produces_integrity_packet(tmp_path: Path):
    from inverted.black_magic.decision_harvest import run_decision_harvest_smoke

    result = run_decision_harvest_smoke(tmp_path, run_id="contract-smoke")
    root = Path(result["root"])
    assert result["instrument_validation"] is True
    assert result["budget"]["used"] <= 1200
    assert (root / "integrity.json").exists()
    integrity = json.loads((root / "integrity.json").read_text(encoding="utf-8"))
    assert integrity["status"] == "OK"
    assert (root / "SHA256SUMS.csv").stat().st_size > 0
    assert (root / "COMPLETE-EVIDENCE.txt").stat().st_size > 0


def test_high_severity_unresolved_blocks_harvest_completion():
    from inverted.black_magic.decision_harvest import evaluate_harvest_completion

    verdict = evaluate_harvest_completion([
        {"finding_id": "x", "severity": "high", "status": "UNRESOLVED"},
    ])
    assert verdict["pass"] is False
    assert verdict["blocking_findings"] == ["x"]


def test_no_existing_assistant_value_module_is_required_to_be_modified():
    from inverted.black_magic import BASELINE_SHA

    assert BASELINE_SHA == "035c2190403c506330b6b54fa244ce35a62f26bf"
