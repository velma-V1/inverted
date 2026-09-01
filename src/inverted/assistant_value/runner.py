from __future__ import annotations

from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any

from . import ARMS, TEST_CALL_CAPS, TEST_NAMES
from .authority import generate_authority_cases, planned_authority_calls, run_authority
from .budget import PhysicalCallBudget
from .evidence import EvidenceStore
from .evidence_trust import generate_evidence_cases, planned_evidence_calls, run_evidence_trust
from .long_horizon import generate_long_horizon_cases, planned_long_horizon_calls, run_long_horizon
from .types import json_safe


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except Exception:
        return None


def _model_metadata(model: Any) -> dict[str, Any]:
    keys = (
        "model",
        "provider",
        "base_url",
        "timeout_s",
        "temperature",
        "max_tokens",
        "max_retries",
        "retry_backoff_s",
        "think",
        "format_json",
        "context_limit",
        "capture_content",
    )
    return {key: json_safe(getattr(model, key, None)) for key in keys}


def _provenance(models: list[Any], *, test_name: str, run_id: str, instrument_validation: bool) -> dict[str, Any]:
    return {
        "test_name": test_name,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "instrument_validation": instrument_validation,
        "models": [_model_metadata(model) for model in models],
    }


def _section(config: dict[str, Any], test_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    root = dict(config.get("assistant_value") or {})
    section = dict(root.get(test_name) or {})
    if not section:
        raise ValueError(f"assistant_value.{test_name} configuration is required")
    return root, section


def _normalize_arms(section: dict[str, Any]) -> tuple[str, ...]:
    arms = tuple(str(x) for x in section.get("arms", ARMS))
    if not arms:
        raise ValueError("at least one assistant-value arm is required")
    if len(set(arms)) != len(arms):
        raise ValueError("assistant-value arm list contains duplicates")
    unknown = set(arms) - set(ARMS)
    if unknown:
        raise ValueError(f"unknown assistant-value arms: {sorted(unknown)}")
    return arms


def _plan(test_name: str, section: dict[str, Any], model_count: int) -> tuple[int, dict[str, Any]]:
    arms = _normalize_arms(section)
    if test_name == "long_horizon":
        per_horizon = int(section.get("per_horizon", 2))
        horizons = tuple(int(x) for x in section.get("horizons", (8, 16, 30)))
        planned = planned_long_horizon_calls(model_count, per_horizon, horizons, len(arms))
        params = {"per_horizon": per_horizon, "horizons": horizons, "arms": arms}
    elif test_name == "evidence_trust":
        cases_per_regime = int(section.get("cases_per_regime", 20))
        planned = planned_evidence_calls(model_count, cases_per_regime, 6, len(arms))
        params = {"cases_per_regime": cases_per_regime, "arms": arms}
    elif test_name == "authority":
        cases_per_class = int(section.get("cases_per_class", 15))
        planned = planned_authority_calls(model_count, cases_per_class, 8, len(arms))
        params = {"cases_per_class": cases_per_class, "arms": arms}
    else:
        raise ValueError(f"unknown assistant-value test: {test_name}")
    if planned < 0:
        raise ValueError("planned physical model calls cannot be negative")
    return planned, params


def run_assistant_value_test(
    test_name: str,
    config: dict[str, Any],
    models: list[Any],
    output_dir: str | Path,
    *,
    run_id: str,
    progress_callback=None,
) -> dict[str, Any]:
    if test_name not in TEST_NAMES:
        raise ValueError(f"unknown assistant-value test: {test_name}")
    if not models:
        raise ValueError("at least one model is required")
    for model in models:
        if getattr(model, "capture_content", True) is not True:
            raise ValueError("assistant-value experiments require capture_content=true for every model")
        internal_retries = int(getattr(model, "max_retries", 0) or 0)
        if internal_retries != 0:
            raise ValueError(
                "assistant-value experiments prohibit adapter internal retries; "
                f"{getattr(model, 'provider', 'unknown')}:{getattr(model, 'model', 'unknown')} "
                f"has max_retries={internal_retries}"
            )

    root_config, section = _section(config, test_name)
    planned, params = _plan(test_name, section, len(models))
    hard_cap = int(TEST_CALL_CAPS[test_name])
    configured_cap = int(section.get("call_cap", hard_cap))
    if configured_cap > hard_cap:
        raise ValueError(f"configured call_cap {configured_cap} exceeds preregistered hard cap {hard_cap} for {test_name}")
    if configured_cap < 0:
        raise ValueError("call_cap must be non-negative")
    if planned > configured_cap:
        raise ValueError(
            f"planned physical model calls {planned} exceed configured cap {configured_cap} "
            f"for {test_name}; refusing before first model call"
        )

    seed = int(root_config.get("seed", 20260901))
    root = Path(output_dir) / "assistant-value" / test_name / str(run_id)
    store = EvidenceStore(root, test_name=test_name, run_id=str(run_id))
    budget = PhysicalCallBudget(test_name, configured_cap)
    instrument_validation = all(str(getattr(model, "provider", "")) == "mock" for model in models)
    preregistration = {
        "test_name": test_name,
        "run_id": str(run_id),
        "status": "INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE" if instrument_validation else "REAL-MODEL EXPERIMENT",
        "deterministic_oracle_is_authority": True,
        "llm_judge_is_ground_truth": False,
        "full_prompt_response_capture_required": True,
        "hard_physical_call_cap": hard_cap,
        "configured_physical_call_cap": configured_cap,
        "planned_physical_calls": planned,
        "seed": seed,
        "arms": list(params["arms"]),
        "parameters": json_safe(params),
    }
    effective_config = {
        "assistant_value": json_safe(root_config),
        "effective_test": test_name,
        "effective_parameters": json_safe(params),
        "model_count": len(models),
        "models": [_model_metadata(model) for model in models],
    }
    provenance = _provenance(models, test_name=test_name, run_id=str(run_id), instrument_validation=instrument_validation)
    store.event("run_started", {"planned_calls": planned, "call_cap": configured_cap, "instrument_validation": instrument_validation})

    if test_name == "long_horizon":
        cases = generate_long_horizon_cases(seed=seed, per_horizon=params["per_horizon"], horizons=params["horizons"])
        trials, metrics, failures = run_long_horizon(
            models=models,
            cases=cases,
            arms=params["arms"],
            run_id=str(run_id),
            budget=budget,
            store=store,
            progress_callback=progress_callback,
        )
    elif test_name == "evidence_trust":
        cases = generate_evidence_cases(seed=seed, cases_per_regime=params["cases_per_regime"])
        trials, metrics, failures = run_evidence_trust(
            models=models,
            cases=cases,
            arms=params["arms"],
            run_id=str(run_id),
            budget=budget,
            store=store,
            progress_callback=progress_callback,
        )
    else:
        cases = generate_authority_cases(seed=seed, cases_per_class=params["cases_per_class"])
        trials, metrics, failures = run_authority(
            models=models,
            cases=cases,
            arms=params["arms"],
            run_id=str(run_id),
            budget=budget,
            store=store,
            progress_callback=progress_callback,
        )

    store.event(
        "run_completed",
        {
            "planned_calls": planned,
            "observed_calls": budget.used,
            "trial_count": len(trials),
            "failure_count": len(failures),
        },
    )
    if budget.used != planned:
        store.append(
            "anomalies",
            {
                "type": "planned_observed_call_mismatch",
                "planned_calls": planned,
                "observed_calls": budget.used,
            },
        )

    paths = store.finalize(
        preregistration=preregistration,
        config=effective_config,
        provenance=provenance,
        metrics=metrics,
        budget=budget.to_dict(),
        trials=trials,
        failures=failures,
    )
    integrity = json.loads((root / "integrity.json").read_text(encoding="utf-8"))
    if integrity.get("status") != "OK":
        raise RuntimeError(f"assistant-value evidence integrity failure at {root}: {integrity}")

    return {
        "test_name": test_name,
        "run_id": str(run_id),
        "root": str(root),
        "planned_calls": planned,
        "metrics": metrics,
        "budget": budget.to_dict(),
        "paths": paths,
        "instrument_validation": instrument_validation,
    }
