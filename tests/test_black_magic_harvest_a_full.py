from __future__ import annotations

import json
from pathlib import Path

import pytest


EXPECTED_CHALLENGES = {
    "shallow_dependency",
    "medium_dependency",
    "deep_dependency",
    "independent_prerequisites",
    "interacting_prerequisites",
    "local_global_trap",
    "stale_state",
    "delayed_state_update",
    "misleading_success",
    "requirement_change",
    "recoverable_wrong_turn",
    "unrecoverable_wrong_turn",
    "preservation_trap",
    "excessive_decomposition",
    "insufficient_decomposition",
    "irrelevant_history",
    "checkpoint_restore",
    "ambiguous_recovery",
    "auditor_false_accept",
    "auditor_false_reject",
}


def test_required_challenge_catalog_is_complete():
    from inverted.black_magic.decision_harvest import REQUIRED_CHALLENGES

    assert set(REQUIRED_CHALLENGES) == EXPECTED_CHALLENGES


def test_case_generation_is_deterministic_and_oracle_is_separate():
    from inverted.black_magic.decision_harvest import generate_decision_harvest_cases

    a = generate_decision_harvest_cases(seed=9, case_count=40)
    b = generate_decision_harvest_cases(seed=9, case_count=40)
    assert a == b
    for case in a:
        public = json.dumps(case["public"], sort_keys=True)
        assert case["oracle"]["correct_action_id"] not in public
        assert "correct_action_id" not in case["public"]
        assert "catastrophic_action_ids" not in case["public"]


def test_case_cycle_covers_every_required_challenge():
    from inverted.black_magic.decision_harvest import REQUIRED_CHALLENGES, generate_decision_harvest_cases

    cases = generate_decision_harvest_cases(seed=11, case_count=len(REQUIRED_CHALLENGES) * 2)
    counts = {challenge: 0 for challenge in REQUIRED_CHALLENGES}
    for case in cases:
        counts[case["challenge"]] += 1
    assert all(value >= 2 for value in counts.values())


def test_derive_system_candidate_uses_only_public_case():
    from inverted.black_magic.decision_harvest import derive_system_candidate

    public = {
        "goal": "Set x to 7 while preserving protected=true",
        "required_path": "x",
        "required_value": 7,
        "preservation": {"protected": True},
        "actions": [
            {"action_id": "good", "path": "x", "value": 7, "touches_protected": False},
            {"action_id": "bad", "path": "x", "value": 8, "touches_protected": False},
            {"action_id": "broad", "path": "x", "value": 7, "touches_protected": True},
        ],
    }
    assert derive_system_candidate(public)["action_id"] == "good"


def test_error_lifecycle_marks_first_and_first_unrecovered_divergence():
    from inverted.black_magic.decision_harvest import trace_error_lifecycle

    decisions = [
        {"index": 0, "correct": True, "recovered": False},
        {"index": 1, "correct": False, "recovered": True},
        {"index": 2, "correct": True, "recovered": False},
        {"index": 3, "correct": False, "recovered": False},
    ]
    trace = trace_error_lifecycle(decisions)
    assert trace["first_divergence"] == 1
    assert trace["first_unrecovered_divergence"] == 3
    assert trace["propagation_depth"] == 1


def test_negative_result_conversion_statuses_are_strict():
    from inverted.black_magic.decision_harvest import classify_negative_result

    assert classify_negative_result(
        severity="high", targeted_flip=True, sham_flip=False, generalized=True, regression=False, interaction=False
    ) == "CONVERTED"
    assert classify_negative_result(
        severity="medium", targeted_flip=False, sham_flip=False, generalized=False, regression=False, interaction=True
    ) == "COMBINED"
    assert classify_negative_result(
        severity="high", targeted_flip=False, sham_flip=False, generalized=False, regression=False, interaction=False
    ) == "UNRESOLVED"
    assert classify_negative_result(
        severity="high", targeted_flip=True, sham_flip=False, generalized=True, regression=True, interaction=False
    ) == "UNRESOLVED"


def test_smoke_metrics_include_all_decision_mechanics_signals(tmp_path: Path):
    from inverted.black_magic.decision_harvest import REQUIRED_METRICS, run_decision_harvest_smoke

    result = run_decision_harvest_smoke(tmp_path, run_id="full-smoke")
    assert set(REQUIRED_METRICS) <= set(result["metrics"])
    assert result["metrics"]["case_count"] >= len(EXPECTED_CHALLENGES)
    assert result["metrics"]["externalized_correction_probe_count"] > 0
    assert result["metrics"]["targeted_replay_count"] > 0
    assert result["metrics"]["sham_replay_count"] > 0


def test_smoke_evidence_contains_required_new_ledgers(tmp_path: Path):
    from inverted.black_magic.decision_harvest import run_decision_harvest_smoke

    result = run_decision_harvest_smoke(tmp_path, run_id="ledger-smoke")
    root = Path(result["root"])
    required = {
        "tasks.jsonl",
        "state_snapshots.jsonl",
        "model_calls.jsonl",
        "prompts.jsonl",
        "responses.jsonl",
        "decisions.jsonl",
        "actions.jsonl",
        "tool_results.jsonl",
        "oracle_results.jsonl",
        "transitions.jsonl",
        "interventions.jsonl",
        "shams.jsonl",
        "error_lifecycle.jsonl",
        "metamorphic_pairs.jsonl",
        "coverage.jsonl",
        "events.jsonl",
        "anomalies.jsonl",
    }
    assert required <= {p.name for p in root.iterdir() if p.is_file()}
    assert (root / "trials.jsonl").stat().st_size > 0
    assert (root / "findings.jsonl").stat().st_size > 0


def test_smoke_has_zero_high_severity_unresolved_findings(tmp_path: Path):
    from inverted.black_magic.decision_harvest import run_decision_harvest_smoke

    result = run_decision_harvest_smoke(tmp_path, run_id="resolved-smoke")
    root = Path(result["root"])
    rows = [json.loads(line) for line in (root / "findings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    blocking = [row for row in rows if row.get("severity") == "high" and row.get("status") == "UNRESOLVED"]
    assert blocking == []


def test_planned_real_matrix_can_use_full_1200_cap():
    from inverted.black_magic.decision_harvest import planned_decision_harvest_actions

    # 3 models x 3 arms x 100 matched decisions + 300 reserved diagnostic/replay actions.
    assert planned_decision_harvest_actions(3, 100, 3, 300) == 1200


def test_harvest_completion_rejects_integrity_or_budget_failure():
    from inverted.black_magic.decision_harvest import evaluate_harvest_completion

    assert evaluate_harvest_completion([], integrity_ok=False)["pass"] is False
    assert evaluate_harvest_completion([], budget_ok=False)["pass"] is False
    assert evaluate_harvest_completion([], integrity_ok=True, budget_ok=True)["pass"] is True
