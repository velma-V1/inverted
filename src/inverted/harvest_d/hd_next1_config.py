from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HDNext1ConfigError(ValueError):
    pass


EXPECTED_MODEL_CAPS = {"SMALL_A": 576, "QWEN": 96}
EXPECTED_QWEN_POOLS = {"calibration": 12, "development": 21, "confirmation": 63}
EXPECTED_QUESTIONS = (
    "Q-MODEL-SUBSTITUTION",
    "Q-MINIMUM-SUPPORT",
    "Q-NEGATIVE-TRANSFER-BOUNDARY",
)
_D3_V1_SEEDS = {20260903, 20260913, 20261003}


def load_hd_next1_config(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HDNext1ConfigError(f"unable to load HD-NEXT-1 config: {path}") from exc
    if not isinstance(raw, dict):
        raise HDNext1ConfigError("HD-NEXT-1 config root must be an object")
    if int(raw.get("schema_version", -1)) != 1:
        raise HDNext1ConfigError("unsupported HD-NEXT-1 config schema")
    if raw.get("experiment_id") != "HD-NEXT-1":
        raise HDNext1ConfigError("experiment_id must be HD-NEXT-1")
    if tuple(raw.get("question_ids") or ()) != EXPECTED_QUESTIONS:
        raise HDNext1ConfigError("HD-NEXT-1 residual question scope is frozen")
    if int(raw.get("max_calls", -1)) != 672:
        raise HDNext1ConfigError("HD-NEXT-1 max_calls must remain 672")
    if dict(raw.get("model_call_caps") or {}) != EXPECTED_MODEL_CAPS:
        raise HDNext1ConfigError("HD-NEXT-1 model call caps are frozen")
    if dict(raw.get("qwen_pools") or {}) != EXPECTED_QWEN_POOLS:
        raise HDNext1ConfigError("HD-NEXT-1 Qwen pool partition is frozen")
    if float(raw.get("effect_margin", -1.0)) != 0.05:
        raise HDNext1ConfigError("HD-NEXT-1 effect margin must remain 0.05")
    if float(raw.get("family_alpha", -1.0)) != 0.05:
        raise HDNext1ConfigError("HD-NEXT-1 family alpha must remain 0.05")
    if bool(raw.get("blind_retries_allowed", True)):
        raise HDNext1ConfigError("blind retries are forbidden")
    if int(raw.get("protected_pool_size", -1)) != 63:
        raise HDNext1ConfigError("protected confirmation pool must remain 63 cases")
    if not isinstance(raw.get("historical_fingerprint"), str) or len(raw["historical_fingerprint"]) != 64:
        raise HDNext1ConfigError("historical fingerprint must be a SHA-256 hex digest")
    models = raw.get("models")
    if not isinstance(models, dict) or not models.get("SMALL_A") or not models.get("QWEN"):
        raise HDNext1ConfigError("SMALL_A and QWEN model tags are required")
    generation = raw.get("generation_options")
    if not isinstance(generation, dict):
        raise HDNext1ConfigError("generation_options must be an object")
    if float(generation.get("temperature", -1.0)) != 0.0:
        raise HDNext1ConfigError("temperature must remain 0")
    if int(generation.get("seed", -1)) != 20260902:
        raise HDNext1ConfigError("generation seed must remain 20260902")
    if int(generation.get("num_ctx", -1)) != 4096:
        raise HDNext1ConfigError("base context must remain 4096")
    seeds = raw.get("seeds")
    if not isinstance(seeds, dict) or set(seeds) != {"development", "fresh", "sealed"}:
        raise HDNext1ConfigError("development/fresh/sealed seeds are required")
    values = [int(seeds[key]) for key in ("development", "fresh", "sealed")]
    if len(set(values)) != 3 or set(values) & _D3_V1_SEEDS:
        raise HDNext1ConfigError("HD-NEXT-1 partition seeds must be fresh and distinct from D3-v1")
    scheduler = raw.get("scheduler")
    if not isinstance(scheduler, dict) or float(scheduler.get("protected_random_stream_fraction", -1.0)) < 0.10:
        raise HDNext1ConfigError("at least 10% protected random/challenger development stream is required")
    calibration = raw.get("reproducibility_calibration")
    if not isinstance(calibration, dict):
        raise HDNext1ConfigError("reproducibility calibration contract is required")
    if (
        int(calibration.get("structurally_distinct_cases", -1)) != 4
        or int(calibration.get("repetitions", -1)) != 3
        or int(calibration.get("physical_call_ceiling", -1)) != 24
    ):
        raise HDNext1ConfigError("calibration must remain 4 cases x 2 models x 3 repetitions = 24 calls")
    return raw
