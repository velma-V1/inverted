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
from .test2_analysis import residual_bottlenecks, threshold_analysis
from .test2_artifacts import Test2ArtifactWriter
from .test2_local import LOCAL_MODELS, PROGRESSIVE_PIPELINES, build_local_plan, run_local_campaign
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
    baseline_successes = int(atlas.get("baseline_successes") or 0)
    baseline_failures = int(atlas.get("baseline_failures") or (base_cells - baseline_successes))
    feasibility = threshold_analysis(
        n=base_cells,
        baseline_successes=baseline_successes,
        recoverable_failures=baseline_failures,
        targets_pp=(target_pp,),
    )[0]
    rows = []
    for effect in atlas.get("standalone_effects", []):
        current_gain = float(effect.get("success_rate", 0.0)) - float(atlas.get("baseline_success_rate", 0.0))
        required = int(feasibility["required_net_recoveries"])
        observed = int(effect.get("net_wins", 0))
        rows.append({
            "component": effect.get("component"),
            "target_pp": target_pp,
            "required_net_recoveries": required,
            "recoverable_baseline_failures": baseline_failures,
            "required_fraction_of_baseline_failures": (
                required / baseline_failures if baseline_failures else 0.0
            ),
            "observed_net_wins": observed,
            "observed_gain": current_gain,
            "observed_fraction_of_required_recoveries": (
                observed / required if required else None
            ),
            "target_already_met": current_gain >= (target_pp / 100.0),
            "globally_feasible_if_failures_are_recoverable": bool(feasibility["feasible"]),
            "max_possible_gain_pp": feasibility["max_possible_gain_pp"],
        })
    return rows


def _model_free_next_stride(atlas: dict[str, Any], run_id: str) -> str:
    standalone = list(atlas.get("standalone_effects", []))
    progressive = list(atlas.get("progressive_effects", []))
    ablations = list(atlas.get("ablation_effects", []))
    saturation = list(atlas.get("candidate_saturation", []))
    independence = dict(atlas.get("candidate_independence") or {})
    ranking = list(atlas.get("order_ranking", []))
    best_overall = ranking[0] if ranking else None
    best_causal = next((row for row in ranking if row.get("causal_status") == "CAUSAL_REPLAY"), None)
    most_recovery = max(standalone, key=lambda row: int(row.get("net_wins", 0)), default=None)
    most_prevention = max(standalone, key=lambda row: int(row.get("failures_prevented", 0)), default=None)
    most_important_ablation = min(ablations, key=lambda row: float(row.get("success_rate", 1.0)), default=None)

    lines = [
        "VELMA TEST 2 — MODEL-FREE NEXT-STRIDE REPORT",
        "================================================",
        f"Run ID: {run_id}",
        f"Evidence scope: {atlas.get('evidence_scope')}",
        f"Base cells: {atlas.get('base_cells')}",
        f"Simulated evaluation units: {atlas.get('trial_units')}",
        "Physical model calls: 0",
        "",
        "CORE HEADROOM",
        f"Baseline success: {float(atlas.get('baseline_success_rate', 0.0)):.6%}",
        f"Full oracle/model-free stack success: {float(atlas.get('full_success_rate', 0.0)):.6%}",
    ]
    if most_recovery:
        lines.append(
            f"Largest standalone recovery upper bound: {most_recovery.get('component')} "
            f"net_wins={most_recovery.get('net_wins')} success={float(most_recovery.get('success_rate', 0.0)):.6%}"
        )
    if most_prevention:
        lines.append(
            f"Largest standalone failure prevention: {most_prevention.get('component')} "
            f"failures_prevented={most_prevention.get('failures_prevented')} "
            f"catastrophics_removed={most_prevention.get('catastrophics_removed')}"
        )
    if most_important_ablation:
        lines.append(
            f"Largest full-stack ablation loss: remove={most_important_ablation.get('removed')} "
            f"remaining_success={float(most_important_ablation.get('success_rate', 0.0)):.6%}"
        )

    lines.extend(["", "CANDIDATE SATURATION"])
    for row in saturation:
        lines.append(
            f"Attempts<={row.get('attempts_available')}: cumulative_success={float(row.get('cumulative_success_rate', 0.0)):.6%} "
            f"marginal_gain_pp={float(row.get('marginal_gain_pp', 0.0)):.4f} "
            f"remaining_failures={row.get('remaining_failures')}"
        )
    if independence:
        lines.append(
            "Three-candidate failure: observed="
            f"{float(independence.get('observed_no_success_in_3_rate', 0.0)):.6%} "
            "independent_expected="
            f"{float(independence.get('independent_expected_no_success_in_3_rate', 0.0)):.6%} "
            f"ratio={independence.get('observed_to_independent_failure_ratio')}"
        )

    lines.extend(["", "PROGRESSIVE COMPOUNDING"])
    for row in progressive:
        lines.append(
            f"Step {row.get('step')} +{row.get('component')}: success={float(row.get('success_rate', 0.0)):.6%} "
            f"net_wins={row.get('net_wins')} prevented={row.get('failures_prevented')} "
            f"catastrophics_removed={row.get('catastrophics_removed')}"
        )

    lines.extend(["", "ORDER BOUNDS"])
    if best_overall:
        lines.append(
            f"Best simulated order: {best_overall.get('order')} "
            f"success={float(best_overall.get('simulated_success_rate', 0.0)):.6%} "
            f"status={best_overall.get('causal_status')}"
        )
    if best_causal:
        lines.append(
            f"Best replay-causal order: {best_causal.get('order')} "
            f"success={float(best_causal.get('simulated_success_rate', 0.0)):.6%}"
        )

    lines.extend([
        "",
        "INTERPRETATION GUARDRAILS",
        "targeted_repair is an ORACLE REPAIR UPPER BOUND in this model-free atlas, not observed model repair performance.",
        "oracle_auditor is an oracle upper bound; its model-free redundancy does not prove a real semantic auditor is useless.",
        "requirement/final validators are deterministic gates: blocked bad output is prevention, not a recovered win.",
        "Order rows marked REQUIRES_NEW_INFERENCE are hypotheses to test locally, not causal replay evidence.",
        "",
        "NEXT STRIDE",
        "Use the bounded five-model local campaign to measure which models realize the formalization, execution, repair, and audit headroom exposed here, while preserving the 480-call ceiling.",
        "",
    ])
    return "\n".join(lines)


def _model_free_evidence(atlas: dict[str, Any], config: dict[str, Any], run_id: str) -> dict[str, Any]:
    standalone = list(atlas.get("standalone_effects", []))
    progressive = list(atlas.get("progressive_effects", []))
    ablations = list(atlas.get("ablation_effects", []))
    pairwise = list(atlas.get("pairwise_interactions", []))
    orderings = list(atlas.get("orderings", []))
    provenance = collect_provenance()
    master_index = {
        "run_id": run_id,
        "mode": "model-free",
        "evidence_scope": atlas.get("evidence_scope"),
        "base_cells": atlas.get("base_cells"),
        "trial_units": atlas.get("trial_units"),
        "baseline_successes": atlas.get("baseline_successes"),
        "baseline_failures": atlas.get("baseline_failures"),
        "baseline_success_rate": atlas.get("baseline_success_rate"),
        "full_successes": atlas.get("full_successes"),
        "full_success_rate": atlas.get("full_success_rate"),
        "physical_model_calls": 0,
        "local_call_ceiling": 480,
        "candidate_independence": atlas.get("candidate_independence"),
    }
    return {
        "master_index": master_index,
        "raw": {
            "trials": list(atlas.get("base_cell_records", [])),
            "model_calls": [], "prompts": [], "responses": [],
            "candidates": list(atlas.get("candidate_records", [])),
            "events": list(atlas.get("component_traces", [])),
            "validator_results": [], "repairs": [],
        },
        "effects": {
            "outcome_transitions": list(atlas.get("outcome_transitions", [])),
            "standalone_effects": standalone,
            "progressive_effects": progressive,
            "ablation_effects": ablations,
            "pairwise_interactions": pairwise,
            "failure_kill_matrix": list(atlas.get("failure_kill_matrix", [])),
            "failure_recovery_matrix": list(atlas.get("failure_recovery_matrix", [])),
            "component_slice_effects": list(atlas.get("component_slice_effects", [])),
            "synergy_matrix": pairwise,
        },
        "order": {
            "every_valid_order": orderings,
            "order_ranking": list(atlas.get("order_ranking", [])),
            "order_slice_ranking": list(atlas.get("order_slice_ranking", [])),
            "saturation": list(atlas.get("saturation", [])),
            "candidate_saturation": list(atlas.get("candidate_saturation", [])),
            "candidate_independence": dict(atlas.get("candidate_independence") or {}),
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
            "environment": provenance,
            "git": {"commit": provenance.get("git_commit")},
            "models": {"mode": "none-model-free"},
        },
        "next_stride_report": _model_free_next_stride(atlas, run_id),
    }


def _router_summary_rows(router: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for level in ("best_single_model", "best_static_role_assignment", "best_task_type_router", "oracle_per_task"):
        value = dict(router.get(level) or {})
        rows.append({
            "router_level": level,
            "successes": value.get("successes", 0),
            "model": value.get("model"),
            "assignments": value.get("assignments"),
        })
    if rows:
        oracle = int(next((row["successes"] for row in rows if row["router_level"] == "oracle_per_task"), 0) or 0)
        for row in rows:
            row["regret_to_oracle_successes"] = oracle - int(row.get("successes") or 0)
    return rows


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
        if row.get("phase") == "progressive_holdout" and row.get("pipeline") == PROGRESSIVE_PIPELINES[4]
    ]
    residual = residual_bottlenecks(best_pipeline_rows)
    router = dict(local.get("layered_router") or {})
    router_rows = _router_summary_rows(router)
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
    next_lines.append("REMAINING BOTTLENECKS IN S4 FULL SPECIALIZATION")
    if residual:
        for i, row in enumerate(residual, start=1):
            next_lines.append(
                f"{i}. {row['failure_class']} count={row['count']} "
                f"perfect-component ceiling gain={row['perfect_component_ceiling_gain']:.6f}"
            )
    else:
        next_lines.append("No residual failures in the evaluated S4 specialized holdout rows.")
    next_lines.extend([
        "",
        "NEXT EXPERIMENT",
        "Target the highest residual recoverable failure class after checking whether its required component is already saturated, redundant, or router-sensitive.",
        "",
    ])

    provenance = collect_provenance()
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
            "failure_recovery_matrix": list(atlas.get("failure_recovery_matrix", [])),
            "component_slice_effects": list(atlas.get("component_slice_effects", [])),
            "synergy_matrix": list(atlas.get("pairwise_interactions", [])),
        },
        "order": {
            "every_valid_order": list(atlas.get("orderings", [])),
            "order_ranking": list(atlas.get("order_ranking", [])),
            "order_slice_ranking": list(atlas.get("order_slice_ranking", [])),
            "saturation": list(atlas.get("saturation", [])),
            "candidate_saturation": list(atlas.get("candidate_saturation", [])),
            "candidate_independence": dict(atlas.get("candidate_independence") or {}),
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
            "router_holdout_results": list(local.get("holdout_pipeline_rows", [])),
            "router_regret": router_rows,
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
            "environment": provenance,
            "git": {"commit": provenance.get("git_commit")},
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
