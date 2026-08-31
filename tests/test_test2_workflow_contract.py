from pathlib import Path


def test_test2_validation_workflow_is_model_free_and_uploads_evidence():
    text = Path(".github/workflows/test2-validation.yml").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "python -m inverted.test2_cli model-free" in text
    assert "actions/upload-artifact" in text
    assert "ollama" not in lowered
    assert "test2-model-free" in text
    assert "pytest" in text
