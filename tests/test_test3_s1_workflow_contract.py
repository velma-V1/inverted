from pathlib import Path


def test_s1_github_workflow_is_mock_only_and_verifies_corrective_protocol():
    path = Path(".github/workflows/test3-s1-validation.yml")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "mock-smoke" in lowered
    assert "--authorize-tier-a" not in lowered
    assert "ollama" not in lowered
    assert "test3-s1-validation-evidence" in lowered
    assert "protocol_valid_for_primary_claim" in lowered
    assert "protocol_revision" in lowered
    assert "s1-r1" in lowered
    assert "holdout" in lowered
    assert "a-r1" in lowered
    assert "physical_model_calls" in lowered
    assert "matched_task_count" in lowered
    assert "intervention_exposure.json" in lowered
    assert "active_intervention" in lowered
    assert "shadow_only" in lowered
