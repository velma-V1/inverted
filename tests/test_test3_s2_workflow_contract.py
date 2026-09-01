from pathlib import Path


def test_s2_validation_workflow_enforces_exact_720_mock_contract():
    text = Path(".github/workflows/test3-s2-validation.yml").read_text(encoding="utf-8")
    lower = text.lower()
    assert "name: test3-s2-validation" in lower
    assert "build/test3-s2-adaptive-routing" in text
    assert 'python-version: "3.14"' in text
    assert "python -m pytest -q" in text
    assert "python -m inverted.test3_s2_cli mock-run" in text
    assert "--config configs/test3-s2.yaml" in text
    assert "test3-s2-ci/mock-validation" in text
    assert "physical_model_calls" in text
    assert "combined_external_actions" in text
    assert "720" in text
    assert "360" in text
    assert "stochastic_divergence.csv" in text
    assert "routing_decisions.csv" in text
    assert "sha256sums.csv" in lower
    assert "actions/upload-artifact@v4" in text
