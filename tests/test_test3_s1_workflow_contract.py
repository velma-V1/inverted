from pathlib import Path


def test_s1_github_workflow_is_mock_only_and_verifies_frozen_r2_exact_200_protocol():
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
    assert "s1-r2" in lowered
    assert "a-r2" in lowered
    assert "physical_model_calls" in lowered
    assert "200" in lowered
    assert "matched_task_count" in lowered
    assert "25" in lowered
    assert "physical_call_cap_per_arm" in lowered
    assert "50" in lowered
    assert "family_summaries.csv" in lowered
    assert "family_count" in lowered
    assert "repair_containment" in lowered
    assert "dependency_order" in lowered
    assert "preservation" in lowered
    assert "execution_ordinal" in lowered
    assert "arm_execution_position" in lowered
    assert "intervention_exposure.json" in lowered
    assert "active_intervention" in lowered
    assert "shadow_only" in lowered
    assert "cache_hit" in lowered
    assert "source_s0_screen_budget" in lowered
    assert "80" in lowered
