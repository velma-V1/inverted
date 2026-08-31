from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any

import yaml

from .artifacts import collect_provenance
from .models import OllamaAdapter
from .test2_analysis import residual_bottlenecks
from .test2_artifacts import Test2ArtifactWriter
from .test2_local import LOCAL_MODELS, build_local_plan, run_local_campaign
from .test2_simulation import run_model_free_atlas


def load_test2_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError("Test-2 config must be a mapping")
    return value


def _run_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:6]}"


def _threshold_rows(atlas: dict[str, Any], target_pp: float) -> list[dict[str, Any]]:
    base_cells = int(atlas.get("base_cells") or 0)
    if not base_cells:
        return []
    target_gain = target_pp / 100.0
    rows = []
    for effect in atlas.get("standalone_effects", []):
        current_gain = float(effect.get("success_rate", 0.0)) - float(atlas.get("baseline_success_rate", 0.0))
        rows.append({
            "component": effect.get("component"),
            "target_pp": target_pp,
            "required_net_recoveries": int((target_gain * base_cells) + 0.999999),
            "observed_net_wins": effect.get("net_wins", 0),
            "observed_gain": current_gain,
            "target_already_met": current_gain >= target_gain,
        })
    return rows


def _model_free_evidence(atlas: dict[str, Any], config: dict[str, Any], run_id: str) -> dict[str, Any]:
    standalone = list(atlas.get("standalone_effects", []))
    progressive = list(atlas.get("progressive_effects", []))
    ablations = list(atlas.get("ablation_effects", []))
    pairwise = list(atlas.get("pairwise_interactions", []))
    orderings = list(atlas.get("orderings", []))
    causal_orders = [row for row in orderings if row.get("causal_status") == "CAUSAL_REPLAY"]
    master_index = {
        "run_id": run_id,
        "mode": "model-free",
        "evidence_scope": atlas.get("evidence_scope"),
        "base_cells": atlas.get("base_cells"),
        "trial_units": atlas.get("trial_units"),
        "physical_model_calls": 0,
        "local_call_ceiling": 480,
    }
    return {
        "master_index": master_index,
        "raw": {
            "trials": list(atlas.get("outcome_transitions", [])),
            "model_calls": [], "prompts": [], "responses": [], "candidates": [],
            "events": [], "validator_results": [], "repairs": [],
        },
        "effects": {
            "outcome_transitions": list(atlas.get("outcome_transitions", [])),
            "standalone_effects": standalone,
            "progressive_effects": progressive,
            "ablation_effects": ablations,
            "pairwise_interactions": pairwise,
            "failure_kill_matrix": list(atlas.get("failure_kill_matrix", [])),
            "synergy_matrix": pairwise,
        },
        "order": {
            "every_valid_order": orderings,
            "order_ranking": causal_orders,
            "saturation": list(atlas.get("saturation", [])),
        },
        "models": {
            "model_task_capability_matrix": [], "model_family_matrix": [],
            "model_fault_matrix": [], "model_complexity_curves": [],
            "model_representation_matrix": [], "model_pair_synergy": [],
            "model_correlated_failures": [], "model_unique_wins": [],
            "role_champions": {}, "router_policy": {},
            "router_holdout_results": [], "router_regret": [],
        },
        "thresholds": {
            "break_even": _threshold_rows(atlas, 0.0),
            "plus_1pp": _threshold_rows(atlas, 1.0),
            "plus_3pp": _threshold_rows(atlas, 3.0),
            "plus_5pp": _threshold_rows(atlas, 5.0),
            "plus_10pp": _threshold_rows(atlas, 10.0),
        },
        "provenance": {
            "config": config,
            "environment": collect_provenance(),
            "git": {"commit": collect_provenance().get("git_commit")},
            "models": {"mode": "none-model-free"},
        },
        "next_stride_report": (
            "VELMA TEST 2 — MODEL-FREE VALIDATION NEXT STRIDE\n"
            "This packet validates deterministic causal-analysis machinery and upper-bound components.\n"
            "It is not local-model architecture evidence. Run the bounded local campaign for model-role conclusions.\n"
        ),
    }


def _local_evidence(local: dict[str, Any], atlas: dict[str, Any], config: dict[str, Any], run_id: str) -> dict[str, Any]:
    records = list(local.get("records", []))
    raw_calls = list(local.get("raw_calls", []))
    model_calls = []
    prompts = []
    responses = []
    for index, call in enumerate(raw_calls):
        call_id = call.get("call_identity") or f"call-{index}"
        telemetry = dict(call.get("telemetry") or {})
        telemetry.update({
            "phase": call.get("phase"), "task_id": call.get("task_id"),
            "call_identity": call_id, "cache_hit": call.get("cache_hit", False),
        })
        model_calls.append(telemetry)
        prompts.append({
            "call_identity": call_id, "phase": call.get("phase"), "task_id": call.get("task_id"),
            "model": call.get("model"), "role": call.get("role"),
            "messages": call.get("prompt"),
            "serialized": json.dumps(call.get("prompt"), ensure_ascii=False, separators=(",", ":")),
        })
        responses.append({
            "call_identity": call_id, "phase": call.get("phase"), "task_id": call.get("task_id"),
            "model": call.get("model"), "role": call.get("role"),
            "text": call.get("response", ""),
        })

    best_pipeline_rows = [
        row for row in records
        if row.get("phase") == "progressive_holdout" and row.get("pipeline") == "specialized_stack"
    ]
    residual = residual_bottlenecks(best_pipeline_rows)
    router = dict(local.get("layered_router") or {})
    master_index = {
        "run_id": run_id,
        "mode": "local",
        "physical_model_calls": local.get("physical_model_calls"),
        "cache_hits": local.get("cache_hits"),
        "hard_call_limit": local.get("hard_call_limit"),
        "models": local.get("models"),
        "phase_limits": local.get("phase_limits"),
        "model_free_trial_units": atlas.get("trial_units"),
        "residual_bottlenecks": residual,
    }

    pair_rows = list(local.get("model_pair_synergy", []))
    role_champions = dict(local.get("role_champions") or {})
    next_lines = [
        "VELMA TEST 2 — NEXT STRIDE REPORT",
        "=================================",
        f"Run ID: {run_id}",
        f"Physical model calls: {local.get('physical_model_calls')}",
        f"Cache hits: {local.get('cache_hits')}",
        "",
        "ROLE CHAMPIONS",
    ]
    for role, model in sorted(role_champions.items()):
        next_lines.append(f"{role}: {model}")
    next_lines.append("")
    next_lines.append("REMAINING BOTTLENECKS")
    if residual:
        for i, row in enumerate(residual, start=1):
            next_lines.append(
                f"{i}. {row['failure_class']} count={row['count']} "
                f"perfect-component ceiling gain={row['perfect_component_ceiling_gain']:.6f}"
            )
    else:
        next_lines.append("No residual failures in the evaluated specialized holdout rows.")
    next_lines.extend([
        "",
        "NEXT EXPERIMENT",
        "Target the highest residual recoverable failure class after checking whether its required component is already saturated or redundant.",
        "",
    ])

    return {
        "master_index": master_index,
        "raw": {
            "trials": records,
            "model_calls": model_calls,
            "prompts": prompts,
            "responses": responses,
            "candidates": list(local.get("candidates", [])),
            "events": list(local.get("events", [])),
            "validator_results": list(local.get("validator_results", [])),
            "repairs": list(local.get("repairs", [])),
        },
        "effects": {
            "outcome_transitions": list(atlas.get("outcome_transitions", [])),
            "standalone_effects": list(atlas.get("standalone_effects", [])),
            "progressive_effects": list(atlas.get("progressive_effects", [])),
            "ablation_effects": list(atlas.get("ablation_effects", [])),
            "pairwise_interactions": list(atlas.get("pairwise_interactions", [])),
            "failure_kill_matrix": list(atlas.get("failure_kill_matrix", [])),
            "synergy_matrix": list(atlas.get("pairwise_interactions", [])),
        },
        "order": {
            "every_valid_order": list(atlas.get("orderings", [])),
            "order_ranking": [row for row in atlas.get("orderings", []) if row.get("causal_status") == "CAUSAL_REPLAY"],
            "saturation": list(atlas.get("saturation", [])),
        },
        "models": {
            "model_task_capability_matrix": list(local.get("capability_by_role_model", [])),
            "model_family_matrix": list(local.get("capability_by_family_model", [])),
            "model_fault_matrix": list(local.get("capability_by_fault_model", [])),
            "model_complexity_curves": list(local.get("capability_by_complexity_model", [])),
            "model_representation_matrix": list(local.get("capability_by_representation_model", [])),
            "model_pair_synergy": pair_rows,
            "model_correlated_failures": pair_rows,
            "model_unique_wins": pair_rows,
            "role_champions": role_champions,
            "router_policy": role_champions,
            "router_holdout_results": best_pipeline_rows,
            "router_regret": [router],
        },
        "thresholds": {
            "break_even": _threshold_rows(atlas, 0.0),
            "plus_1pp": _threshold_rows(atlas, 1.0),
            "plus_3pp": _threshold_rows(atlas, 3.0),
            "plus_5pp": _threshold_rows(atlas, 5.0),
            "plus_10pp": _threshold_rows(atlas, 10.0),
        },
        "provenance": {
            "config": config,
            "environment": collect_provenance(),
            "git": {"commit": collect_provenance().get("git_commit")},
            "models": {"configured": list(LOCAL_MODELS)},
        },
        "next_stride_report": "\n".join(next_lines),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VELMA Inverted Test 2 — Compounding Causal Atlas")
    sub = parser.add_subparsers(dest="mode", required=True)

    model_free = sub.add_parser("model-free", help="run deterministic/GitHub-safe Test-2 atlas")
    model_free.add_argument("--config", required=True)
    model_free.add_argument("--output-dir", default="test2-runs")
    model_free.add_argument("--run-id")
    model_free.add_argument("--seed-count", type=int)

    local = sub.add_parser("local", help="run bounded five-model Ollama Test-2 campaign")
    local.add_argument("--config", required=True)
    local.add_argument("--output-dir", default="test2-runs")
    local.add_argument("--run-id")
    local.add_argument("--dry-plan", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cfg = load_test2_config(args.config)

    if args.mode == "model-free":
        run_id = args.run_id or _run_id("test2-model-free")
        seed_count = int(args.seed_count or cfg.get("model_free", {}).get("seed_count", 100))
        atlas = run_model_free_atlas(seed_count=seed_count)
        evidence = _model_free_evidence(atlas, cfg, run_id)
        run_dir = Path(args.output_dir) / run_id
        Test2ArtifactWriter(run_dir).write_all(evidence)
        print(f"RUN_ID={run_id}")
        print(f"MODEL_FREE_BASE_CELLS={atlas['base_cells']}")
        print(f"MODEL_FREE_TRIAL_UNITS={atlas['trial_units']}")
        print(f"EVIDENCE_DIR={run_dir}")
        return 0

    local_cfg = cfg.get("local", {})
    configured_models = tuple(local_cfg.get("models") or ())
    if configured_models != LOCAL_MODELS:
        raise ValueError(f"local config models must be exactly {LOCAL_MODELS!r}")
    hard_limit = int(local_cfg.get("hard_call_limit", 480))
    if hard_limit != 480:
        raise ValueError("Test-2 local hard_call_limit must be exactly 480")
    if bool(local_cfg.get("early_stop", False)):
        raise ValueError("Test-2 local early_stop must be false")

    plan = build_local_plan()
    if args.dry_plan:
        print("TEST2_LOCAL_DRY_PLAN")
        for model in plan.models:
            print(model)
        for phase, limit in cfg.get("local", {}).get("phase_limits", {}).items():
            print(f"PHASE {phase} MAX_CALLS={limit}")
        print(f"PLANNED_MAX_PHYSICAL_CALLS={plan.planned_max_physical_calls}")
        return 0

    run_id = args.run_id or _run_id("test2-local")
    settings = local_cfg.get("ollama", {})
    models = [
        OllamaAdapter(
            model=name,
            base_url=str(settings.get("base_url", "http://127.0.0.1:11434")),
            timeout_s=float(settings.get("timeout_s", 600)),
            capture_content=True,
            temperature=float(settings.get("temperature", 0)),
            max_tokens=int(settings.get("max_tokens", 1024)),
            max_retries=int(settings.get("transport_retries", 2)),
            retry_backoff_s=float(settings.get("retry_backoff_s", 5)),
            think=settings.get("think", False),
            format_json=True,
            context_limit=int(settings.get("context_limit", 8192)),
        )
        for name in configured_models
    ]
    local = run_local_campaign(models, run_id=run_id, hard_limit=hard_limit)
    atlas = run_model_free_atlas(seed_count=int(cfg.get("model_free", {}).get("seed_count_for_local", 10)))
    evidence = _local_evidence(local, atlas, cfg, run_id)
    run_dir = Path(args.output_dir) / run_id
    Test2ArtifactWriter(run_dir).write_all(evidence)
    print(f"RUN_ID={run_id}")
    print(f"PHYSICAL_MODEL_CALLS={local['physical_model_calls']}")
    print(f"CACHE_HITS={local['cache_hits']}")
    print(f"HARD_CALL_LIMIT={hard_limit}")
    print(f"EVIDENCE_DIR={run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
