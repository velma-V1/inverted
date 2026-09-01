from pathlib import Path

import pytest
import yaml

from inverted.models import OllamaAdapter
from inverted.assistant_value.runner import run_assistant_value_test


def _config():
    return {
        "assistant_value": {
            "capture_content": True,
            "seed": 20260901,
            "long_horizon": {
                "call_cap": 1152,
                "per_horizon": 1,
                "horizons": [1],
                "arms": ["DIRECT"],
            },
        }
    }


def test_runner_rejects_adapter_internal_retries_before_first_call(tmp_path):
    model = OllamaAdapter(
        model="never-called",
        base_url="http://127.0.0.1:1",
        capture_content=True,
        max_retries=1,
    )
    with pytest.raises(ValueError, match="internal retries"):
        run_assistant_value_test(
            "long_horizon",
            _config(),
            [model],
            tmp_path,
            run_id="retry-rejected",
        )


def test_real_model_config_disables_internal_retries():
    raw = yaml.safe_load(Path("configs/assistant-value-local.yaml").read_text(encoding="utf-8"))
    ollama_models = [model for model in raw["models"] if model["provider"] == "ollama"]
    assert ollama_models
    assert all(int(model.get("max_retries", 0)) == 0 for model in ollama_models)
