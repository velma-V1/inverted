from pathlib import Path


def test_testing_policy_freezes_universal_test_automation_rule():
    text = Path("TESTING.md").read_text(encoding="utf-8").lower()

    assert "universal test-automation rule" in text
    assert "automated wherever technically and scientifically possible" in text
    assert "automation is the default" in text
    assert "preflight" in text
    assert "test execution" in text
    assert "evidence capture" in text
    assert "crash-safe checkpoint/resume" in text
    assert "final completeness/quality validation" in text
    assert "human intervention" in text
    assert "must never silently change the scientific design" in text


def test_testing_policy_freezes_same_terminal_compact_progress_contract():
    text = Path("TESTING.md").read_text(encoding="utf-8").lower()

    assert "universal campaign progress rule" in text
    assert "same-terminal requirement" in text
    assert "same terminal session" in text
    assert "narrow split-window layout" in text
    assert "visible progress bar" in text
    assert "percent completed" in text
    assert "work/tasks completed" in text
    assert "work/tasks remaining" in text
    assert "completed/total work units" in text
    assert "physical model calls used/available" in text
    assert "estimated time to completion / time remaining" in text
    assert "eta clock time" in text
    assert "adaptive or sequential tests" in text
    assert "split-window / repaint bug tolerance" in text
    assert "throttle updates" in text
    assert "fall back automatically" in text
    assert "progress regression requirement" in text
    assert "progress reporting must not alter" in text
    assert "scientific accounting" in text


def test_testing_policy_freezes_universal_1000_action_ceiling():
    text = Path("TESTING.md").read_text(encoding="utf-8").lower()

    assert "universal per-test external-action ceiling" in text
    assert "1000" in text
    assert "combined total" in text
    assert "model calls" in text
    assert "ai/agent actions" in text
    assert "api calls" in text
    assert "tool calls" in text
    assert "single shared budget" in text
    assert "fail closed" in text
    assert "preflight" in text
    assert "actual usage" in text
    assert "must not exceed" in text
    assert "ceiling, not a quota" in text
    assert "orthogonal variety" in text
    assert "failure classes" in text
    assert "interventions" in text
    assert "models/roles" in text
    assert "perturbations" in text
    assert "counterfactuals" in text
    assert "validators" in text
    assert "stress conditions" in text
    assert "redundant repetition" in text
    assert "information gain" in text
