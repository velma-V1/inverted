from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

from . import ARMS, HARVEST_CAPS
from .budget import ExternalActionBudget
from .decision_harvest import (
    evaluate_harvest_completion,
    generate_decision_harvest_cases,
    planned_decision_harvest_actions,
    run_decision_harvest,
)
from .evidence import BlackMagicEvidenceStore
from .types import json_safe


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip() or None
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


def _normalize_arms(value: Any) -> tuple[str, ...]:
    arms = tuple(str(x) for x in (value or ARMS))
    if not arms or len(set(arms)) != len(arms):
        raise ValueError("decision harvest arms must be non-empty and unique")
    unknown = set(arms) - set(ARMS)
    if unknown:
        raise ValueError(f"unknown decision harvest arms: {sorted(unknown)}")
    return arms


def run_decision_harvest_from_config(
    config: dict[str, Any],
    models: list[Any],
    output_dir: str | Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    if not models:
        raise ValueError("decision harvest requires at least one model")
    for model in models:
        if getattr(model, "capture_content", True) is not True:
            raise ValueError("black-magic experiments require capture_content=true")
        if int(getattr(model, "max_retries", 0) or 0) != 0:
            raise ValueError("black-magic experiments prohibit adapter internal retries")

    root_cfg = dict(config.get("black_magic") or {})
    section = dict(root_cfg.get("decision_harvest") or {})
    if not section:
        raise ValueError("black_magic.decision_harvest configuration is required")
    seed = int(root_cfg.get("seed", 20260901))
    case_count = int(section.get("case_count", 100))
    diagnostic_reserve = int(section.get("diagnostic_reserve", 300))
    arms = _normalize_arms(section.get("arms"))
    hard_cap = int(HARVEST_CAPS["decision_harvest"])
    configured_cap = int(section.get("action_cap", hard_cap))
    if configured_cap > hard_cap:
        raise ValueError(f"configured action_cap {configured_cap} exceeds immutable hard cap {hard_cap}")
    mandatory_diagnostics = 4 * len(models)
    if diagnostic_reserve < mandatory_diagnostics:
        raise ValueError(
            f"diagnostic_reserve {diagnostic_reserve} cannot cover mandatory externalized-correction probes {mandatory_diagnostics}"
        )
    planned = planned_decision_harvest_actions(len(models), case_count, len(arms), diagnostic_reserve)
    if planned > configured_cap:
        raise ValueError(
            f"planned external actions {planned} exceed configured cap {configured_cap}; refusing before first call"
        )

    root = Path(output_dir) / "black-magic" / "decision_harvest" / str(run_id)
    store = BlackMagicEvidenceStore(root, experiment_name="decision_harvest", run_id=str(run_id))
    budget = ExternalActionBudget("decision_harvest", configured_cap)
    cases = generate_decision_harvest_cases(seed=seed, case_count=case_count)
    instrument_validation = all(str(getattr(model, "provider", "")) == "mock" for model in models)
    store.event("run_started", {"planned_external_actions": planned, "configured_cap": configured_cap})
    trials, metrics, findings = run_decision_harvest(
        models=models,
        cases=cases,
        arms=arms,
        run_id=str(run_id),
        budget=budget,
        store=store,
    )
    completion = evaluate_harvest_completion(findings, budget_ok=budget.used <= budget.cap)
    metrics["completion"] = completion
    store.event("run_completed", {"trials": len(trials), "findings": len(findings), "used": budget.used})
    preregistration = {
        "experiment": "decision_harvest",
        "status": "INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE" if instrument_validation else "REAL-MODEL EVIDENCE HARVEST",
        "hard_external_action_cap": hard_cap,
        "configured_external_action_cap": configured_cap,
        "planned_max_external_actions": planned,
        "diagnostic_reserve": diagnostic_reserve,
        "deterministic_oracle_is_authority": True,
        "llm_judge_is_ground_truth": False,
        "hidden_oracle_model_visible": False,
        "seed": seed,
        "arms": list(arms),
    }
    provenance = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "instrument_validation": instrument_validation,
        "models": [_model_metadata(model) for model in models],
    }
    finalized = store.finalize(
        preregistration=preregistration,
        config={"black_magic": json_safe(root_cfg), "effective_case_count": case_count, "effective_arms": list(arms)},
        provenance=provenance,
        metrics=metrics,
        budget=budget.to_dict(),
        trials=trials,
        findings=findings,
    )
    if finalized["integrity"]["status"] != "OK":
        raise RuntimeError(f"decision harvest evidence integrity failure: {finalized['integrity']}")
    if not completion["pass"]:
        raise RuntimeError(f"decision harvest completion gate failed: {completion}")
    return {
        "stage": "decision_harvest",
        "run_id": str(run_id),
        "root": str(root),
        "planned_external_actions": planned,
        "budget": budget.to_dict(),
        "metrics": metrics,
        "instrument_validation": instrument_validation,
    }
