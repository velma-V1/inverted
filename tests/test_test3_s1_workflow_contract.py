from pathlib import Path


def test_s1_github_workflow_is_mock_only_and_never_authorizes_tier_a():
    path = Path(".github/workflows/test3-s1-validation.yml")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "mock-smoke" in lowered
    assert "--authorize-tier-a" not in lowered
    assert "ollama" not in lowered
    assert "test3-s1-validation-evidence" in lowered
