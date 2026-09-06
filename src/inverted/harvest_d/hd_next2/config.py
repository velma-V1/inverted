from __future__ import annotations

import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

from .types import StageId


class HDNext2ConfigError(ValueError):
    pass


def _required_integer(raw: dict[str, Any], field: str) -> int:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HDNext2ConfigError(f"{field} must be an integer")
    return value


def _required_number(raw: dict[str, Any], field: str) -> Real:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise HDNext2ConfigError(f"{field} must be a finite number")
    return value


def load_hd_next2_config(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HDNext2ConfigError(f"unable to load HD-NEXT-2A config: {path}") from exc
    if not isinstance(raw, dict):
        raise HDNext2ConfigError("HD-NEXT-2A config root must be an object")
    if raw.get("experiment_id") != "HD-NEXT-2A":
        raise HDNext2ConfigError("experiment_id must be HD-NEXT-2A")
    if _required_integer(raw, "combined_action_ceiling") > 1000:
        raise HDNext2ConfigError("combined action ceiling cannot exceed 1000")
    if _required_integer(raw, "non_model_action_reserve") < 40:
        raise HDNext2ConfigError("non-model action reserve must be at least 40")
    if _required_number(raw, "protected_exploration_fraction") < 0.20:
        raise HDNext2ConfigError("protected exploration fraction must be at least 0.20")
    if not isinstance(raw.get("blind_retries_allowed"), bool):
        raise HDNext2ConfigError("blind_retries_allowed must be a boolean")
    if raw["blind_retries_allowed"]:
        raise HDNext2ConfigError("blind retries are forbidden")
    models = raw.get("models")
    expected_models = {
        "SMALL_A": "qwen2.5:1.5b-instruct-q8_0",
        "QWEN": "qwen3.5:9b-q8_0",
        "DEVSTRAL_24B": "devstral-small-2:24b",
    }
    if models != expected_models:
        raise HDNext2ConfigError("SMALL_A, QWEN, and DEVSTRAL_24B models are frozen")
    if not raw.get("primary_model") or raw["primary_model"] not in {"SMALL_A", "QWEN"}:
        raise HDNext2ConfigError("a primary model is required")
    stages = raw.get("stages")
    valid_stages = {stage.value for stage in StageId}
    if not isinstance(stages, list) or not set(stages) <= valid_stages:
        raise HDNext2ConfigError("stages must contain only known HD-NEXT-2A stages")
    return raw
