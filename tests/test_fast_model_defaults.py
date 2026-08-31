from pathlib import Path


def test_outer_handoff_defaults_to_faster_three_model_trio():
    text = Path("scripts/run-overnight-handoff.ps1").read_text(encoding="utf-8").lower()
    assert '[string]$model1 = "qwen3.5:9b-q8_0"' in text
    assert '[string]$model2 = "llama3.1:8b"' in text
    assert '[string]$model3 = "phi4-mini:3.8b"' in text
