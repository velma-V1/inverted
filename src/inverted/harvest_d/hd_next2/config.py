from __future__ import annotations

import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from .types import StageId


class HDNext2ConfigError(ValueError):
    pass


def _required_integer(raw: Mapping[str, Any], field: str) -> int:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HDNext2ConfigError(f"{field} must be an integer")
    return value


def _required_number(raw: Mapping[str, Any], field: str) -> Real:
    value = raw.get(field)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise HDNext2ConfigError(f"{field} must be a finite number")
    return value



def canonical_a0_planner_config() -> dict[str, Any]:
    return {
        "experiment_id": "HD-NEXT-2A",
        "combined_action_ceiling": 1000,
        "non_model_action_reserve": 40,
        "blind_retries_allowed": False,
        "models": {
            "SMALL_A": "qwen2.5:1.5b-instruct-q8_0",
            "QWEN": "qwen3.5:9b-q8_0",
            "DEVSTRAL_24B": "devstral-small-2:24b",
        },
        "a0": {
            "development_seed": 20260921,
            "anchor_case_count": 8,
            "replications_per_cell": 4,
            "treatment_kinds": ["RAW", "HISTORICAL_SEED"],
            "diagnostic_model": "DEVSTRAL_24B",
            "non_model_action_forecast": 40,
        },
    }


def validate_a0_planner_config(raw: Mapping[str, Any]) -> None:
    expected = canonical_a0_planner_config()
    if raw.get("experiment_id") != expected["experiment_id"]:
        raise HDNext2ConfigError("experiment_id must be HD-NEXT-2A")
    if _required_integer(raw, "combined_action_ceiling") > 1000:
        raise HDNext2ConfigError("combined action ceiling cannot exceed 1000")
    reserve = _required_integer(raw, "non_model_action_reserve")
    if reserve < 40:
        raise HDNext2ConfigError("non-model action reserve must be at least 40")
    if raw.get("blind_retries_allowed") is not False:
        raise HDNext2ConfigError("blind retries are forbidden")
    if raw.get("models") != expected["models"]:
        raise HDNext2ConfigError("SMALL_A, QWEN, and DEVSTRAL_24B models are frozen")
    a0 = raw.get("a0")
    if isinstance(a0, Mapping) and type(a0.get("non_model_action_forecast")) is int and a0["non_model_action_forecast"] < reserve:
        raise HDNext2ConfigError("A0 non-model action forecast must cover the top-level reserve")
    if a0 != expected["a0"]:
        raise HDNext2ConfigError("Stage 2A-0 design must match the frozen Test-1 calibration")

def load_hd_next2_config(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HDNext2ConfigError(f"unable to load HD-NEXT-2A config: {path}") from exc
    if not isinstance(raw, dict):
        raise HDNext2ConfigError("HD-NEXT-2A config root must be an object")
    validate_a0_planner_config(raw)
    if _required_number(raw, "protected_exploration_fraction") < 0.20:
        raise HDNext2ConfigError("protected exploration fraction must be at least 0.20")
    if not raw.get("primary_model") or raw["primary_model"] not in {"SMALL_A", "QWEN"}:
        raise HDNext2ConfigError("a primary model is required")
    stages = raw.get("stages")
    valid_stages = {stage.value for stage in StageId}
    if not isinstance(stages, list) or not set(stages) <= valid_stages:
        raise HDNext2ConfigError("stages must contain only known HD-NEXT-2A stages")
    return raw
