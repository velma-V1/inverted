from __future__ import annotations

QWEN_MODEL = "qwen3.5:9b-q8_0"
QWEN_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 1.5,
    "repeat_penalty": 1.0,
    "num_ctx": 8192,
    "num_predict": 1024,
}
CAMPAIGN_RUN_CEILING = 200
DEFAULT_FRONTIER_POOL = 60
DEFAULT_HARVEST_CASES = 20
DEFAULT_FRESH_HOLDOUT = 24
