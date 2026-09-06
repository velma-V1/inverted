from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import StageId


class HDNext2ConfigError(ValueError):
    pass


def load_hd_next2_config(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HDNext2ConfigError(f"unable to load HD-NEXT-2A config: {path}") from exc
    if not isinstance(raw, dict):
        raise HDNext2ConfigError("HD-NEXT-2A config root must be an object")
    if raw.get("experiment_id") != "HD-NEXT-2A":
        raise HDNext2ConfigError("experiment_id must be HD-NEXT-2A")
    if int(raw.get("combined_action_ceiling", -1)) > 1000:
        raise HDNext2ConfigError("combined action ceiling cannot exceed 1000")
    if int(raw.get("non_model_action_reserve", -1)) < 40:
        raise HDNext2ConfigError("non-model action reserve must be at least 40")
    if float(raw.get("protected_exploration_fraction", -1.0)) < 0.20:
        raise HDNext2ConfigError("protected exploration fraction must be at least 0.20")
    if bool(raw.get("blind_retries_allowed", True)):
        raise HDNext2ConfigError("blind retries are forbidden")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"SMALL_A", "QWEN", "DEVSTRAL_24B"}:
        raise HDNext2ConfigError("SMALL_A, QWEN, and DEVSTRAL_24B models are required")
    if not raw.get("primary_model") or raw["primary_model"] not in {"SMALL_A", "QWEN"}:
        raise HDNext2ConfigError("a primary model is required")
    stages = raw.get("stages")
    valid_stages = {stage.value for stage in StageId}
    if not isinstance(stages, list) or not set(stages) <= valid_stages:
        raise HDNext2ConfigError("stages must contain only known HD-NEXT-2A stages")
    return raw
