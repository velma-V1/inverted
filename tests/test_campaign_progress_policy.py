from pathlib import Path


def test_testing_policy_freezes_universal_campaign_progress_rule():
    text = Path("TESTING.md").read_text(encoding="utf-8").lower()

    assert "universal campaign progress rule" in text
    assert "every future campaign section" in text
    assert "enabled by default" in text
    assert "completed/total work units" in text
    assert "physical model calls used/total" in text
    assert "current arm/phase" in text
    assert "percent complete" in text
    assert "elapsed time" in text
    assert "estimated time remaining" in text
    assert "eta clock time" in text
    assert "flush" in text
    assert "display-only telemetry" in text
    assert "must not alter" in text
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
