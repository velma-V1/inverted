from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import yaml

from .models import MockModelAdapter, OllamaAdapter
from .test2_provenance import collect_ollama_provenance
from .test3_s1_analysis import derive_s1_verdict, summarize_s1
from .test3_s1_artifacts import Test3S1ArtifactWriter
from .test3_s1_cases import build_holdout_a_r1
from .test3_s1_inputs import S1ResolvedInputs, load_s1_inputs
from .test3_s1_progress import InPlaceS1Progress, ProgressReportingAdapter, S1ProgressTracker
from .test3_s1_runtime import (
    S1_CALLS_PER_ARM_TASK,
    S1_HOLDOUT,
    S1_PROTOCOL_REVISION,
    matched_task_limit,
    run_s1_screen,
)


PREDECESSOR_INVALID_RUN = "test3-s1-20260901-111233"
PREDECESSOR_INVALIDATION = "INTERVENTION_EXPOSURE_COLLAPSE"
S1_R1_MATCHED_TASKS = 10


def _load_config(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict) or not isinstance(value.get("s1"), dict):
        raise ValueError("Test3 S1 config must contain an s1 mapping")
    s1 = dict(value["s1"])
    expected = {
        "section": "S1_FIXED_STACK_ORDER",
        "protocol_revision": S1_PROTOCOL_REVISION,
        "holdout": S1_HOLDOUT,
        "hard_call_limit": 80,
        "arm_count": 4,
        "per_arm_call_cap": 20,
        "matched_tasks": S1_R1_MATCHED_TASKS,
        "calls_per_arm_task": S1_CALLS_PER_ARM_TASK,
        "intervention_start": "deterministic_verified_failure",
        "predecessor_invalid_run": PREDECESSOR_INVALID_RUN,
        "predecessor_invalidation": PREDECESSOR_INVALIDATION,
    }
    for key, required in expected.items():
        if s1.get(key) != required:
            raise ValueError(f"S1-R1 config {key} must be exactly {required!r}")
    if s1.get("no_outcome_dependent_early_stopping") is not True:
        raise ValueError("S1-R1 forbids outcome-dependent early stopping")
    ollama = dict(s1.get("ollama") or {})
    if int(ollama.get("transport_retries") or 0) != 0:
        raise ValueError("S1-R1 Ollama transport retries must be zero")
    if int(s1["matched_tasks"]) * int(s1["arm_count"]) * int(s1["calls_per_arm_task"]) != int(s1["hard_call_limit"]):
        raise ValueError("S1-R1 schedule must resolve to exactly 80 physical calls")
    return value


def _mock_arms() -> tuple[dict[str, Any], ...]:
    return (
        {"arm_id": "S1-A0", "role": "best_single_model_baseline", "order": None, "physical_call_cap": 20},
        {"arm_id": "S1-A1", "role": "current_best_fixed_hybrid", "order": "requirement_validator -> retry -> targeted_repair -> final_validator", "physical_call_cap": 20},
        {"arm_id": "S1-A2", "role": "alternate_fixed_order", "order": "requirement_validator -> targeted_repair -> final_validator -> retry", "physical_call_cap": 20},
        {"arm_id": "S1-A3", "role": "random_order_negative_control", "order": "retry -> targeted_repair -> final_validator -> requirement_validator", "physical_call_cap": 20},
    )


def _execution_preregistration(resolved: S1ResolvedInputs, config: dict[str, Any]) -> dict[str, Any]:
    s1 = dict(config["s1"])
    source = dict(resolved.preregistration)
    return {
        "status": "S1_R1_FROZEN_FOR_LOCAL_TIER_A_EXECUTION",
        "section": "S1_FIXED_STACK_ORDER",
        "protocol_revision": S1_PROTOCOL_REVISION,
        "holdout": S1_HOLDOUT,
        "source_s0_holdout": resolved.holdout,
        "corrective_reason": PREDECESSOR_INVALIDATION,
        "predecessor_invalid_run": PREDECESSOR_INVALID_RUN,
        "predecessor_invalid_for_primary_claim": True,
        "source_s0_preregistration": source,
        "arms": [dict(row) for row in resolved.arms],
        "arm_count": len(resolved.arms),
        "exact_budget": resolved.exact_budget,
        "physical_call_cap_per_arm": resolved.per_arm_call_cap,
        "matched_tasks": int(s1["matched_tasks"]),
        "calls_per_arm_task": int(s1["calls_per_arm_task"]),
        "intervention_start": s1["intervention_start"],
        "budget_strategy": "exact_equal_physical_call_intervention_screen",
        "no_outcome_dependent_early_stopping": True,
        "tier_a_inference_authorized_by_artifact": False,
        "full_power_cluster_requirement": resolved.full_power_clusters,
        "screen_is_underpowered_for_target_effect": True,
    }


def _report(verdict: dict[str, Any], runtime: dict[str, Any]) -> str:
    lines = [
        "VELMA TEST 3 — SECTION 1 R1 FIXED STACK/ORDER",
        "=============================================",
        f"Run ID: {runtime.get('run_id')}",
        f"Protocol: {runtime.get('protocol_revision')}",
        f"Holdout: {runtime.get('holdout')}",
        f"Physical model calls: {runtime.get('physical_model_calls', 0)} / {runtime.get('exact_budget', 80)}",
        f"Matched Holdout A-R1 tasks: {runtime.get('matched_task_limit', 0)}",
        f"Protocol valid for primary claim: {str(bool(verdict.get('protocol_valid_for_primary_claim'))).lower()}",
        f"Verdict: {verdict.get('verdict')}",
        f"Reason: {verdict.get('reason', '')}",
        f"Tier-A architecture claim: {str(bool(verdict.get('tier_a_architecture_claim'))).lower()}",
        "",
    ]
    return "\n".join(lines)


def _assemble_evidence(
    *,
    runtime: dict[str, Any],
    preregistration: dict[str, Any],
    config: dict[str, Any],
    provenance: dict[str, Any],
    full_power_clusters: int | None,
    mock: bool = False,
) -> dict[str, Any]:
    analysis = summarize_s1(runtime["trials"])
    verdict = derive_s1_verdict(analysis, full_power_clusters=full_power_clusters)
    if mock and analysis.get("protocol_valid_for_primary_claim") is True:
        verdict = {
            "verdict": "MOCK_VALIDATION_ONLY",
            "reason": "GitHub/mock S1-R1 validation exercised the exact-80-call corrective instrument without real model inference.",
            "tier_a_architecture_claim": False,
            "real_model_inference": False,
            "protocol_valid_for_primary_claim": True,
            "protocol_revision": S1_PROTOCOL_REVISION,
            "holdout": S1_HOLDOUT,
            "matched_task_count": analysis["matched_task_count"],
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": True,
        }
    verdict["physical_model_calls"] = int(runtime["physical_model_calls"])
    verdict.setdefault("protocol_revision", runtime.get("protocol_revision"))
    verdict.setdefault("holdout", runtime.get("holdout"))
    verdict.setdefault("protocol_valid_for_primary_claim", analysis.get("protocol_valid_for_primary_claim", False))

    edge_cases: list[dict[str, Any]] = [{
        "kind": "measurement_protocol_failure",
        "classification": "predecessor_s1_intervention_exposure_collapse",
        "run_id": PREDECESSOR_INVALID_RUN,
        "invalid_for_primary_claim": True,
        "discovery_reason": (
            "The predecessor S1 run consumed 24 calls over 6 matched tasks because successful initial executor outputs "
            "caused fixed-order interventions to disappear. It is retained as measurement-system evidence and excluded from R1 claims."
        ),
    }]
    if full_power_clusters is not None and analysis["matched_task_count"] < full_power_clusters:
        edge_cases.append({
            "kind": "power_boundary",
            "classification": "bounded_s1_r1_screen_underpowered_for_target_effect",
            "matched_task_count": analysis["matched_task_count"],
            "full_power_cluster_requirement": full_power_clusters,
            "discovery_reason": "The exact-80-call S1-R1 screen is a large-effect screen and cannot exclude the configured small target effect.",
        })

    return {
        "preregistration": preregistration,
        "config": config,
        "provenance": provenance,
        "model_calls": runtime["model_calls"],
        "events": runtime["events"],
        "trials": runtime["trials"],
        "validator_results": runtime["validator_results"],
        "arm_accounting": runtime["arm_accounting"],
        "arm_summaries": analysis["arm_summaries"],
        "pairwise_effects": analysis["pairwise_effects"],
        "transitions": analysis["transitions"],
        "intervention_exposure": analysis["intervention_exposure"],
        "protocol_failures": analysis["protocol_failures"],
        "edge_cases": edge_cases,
        "instrumentation_anomalies": [],
        "verdict": verdict,
        "report": _report(verdict, runtime),
        "real_model_inference": bool(runtime.get("real_model_inference")),
    }


def _adapter(name: str, settings: dict[str, Any]) -> OllamaAdapter:
    return OllamaAdapter(
        model=name,
        base_url=str(settings.get("base_url") or "http://127.0.0.1:11434"),
        timeout_s=float(settings.get("timeout_s") or 600),
        temperature=float(settings.get("temperature") or 0),
        max_tokens=int(settings.get("max_tokens") or 1024),
        max_retries=int(settings.get("transport_retries") or 0),
        retry_backoff_s=float(settings.get("retry_backoff_s") or 0),
        think=settings.get("think", False),
        format_json=bool(settings.get("format_json", True)),
        context_limit=int(settings.get("context_limit") or 8192),
        capture_content=True,
    )


def _provenance_snapshot(base_url: str, model_names: tuple[str, ...]) -> dict[str, Any]:
    snapshot = collect_ollama_provenance(base_url, model_names)
    models = snapshot.get("models") if isinstance(snapshot, dict) else None
    if not isinstance(models, dict) or set(models) != set(model_names):
        raise ValueError("S1 Ollama identity preflight did not resolve exactly the frozen selected models")
    for name in model_names:
        row = models.get(name) or {}
        if str(row.get("requested_name") or "") != name or not str(row.get("tag_digest") or ""):
            raise ValueError(f"S1 Ollama identity preflight failed for {name}")
    return snapshot


def _dry_plan(resolved: S1ResolvedInputs) -> None:
    cases = build_holdout_a_r1()
    matched = matched_task_limit(resolved.arms, available_cases=len(cases))
    planned = len(resolved.arms) * matched * S1_CALLS_PER_ARM_TASK
    print("SECTION=S1_FIXED_STACK_ORDER")
    print(f"PROTOCOL={S1_PROTOCOL_REVISION}")
    print(f"HOLDOUT={S1_HOLDOUT}")
    print(f"EXACT_BUDGET={resolved.exact_budget}")
    print(f"ARM_COUNT={len(resolved.arms)}")
    print(f"PER_ARM_CALL_CAP={resolved.per_arm_call_cap}")
    print(f"MATCHED_TASKS={matched}")
    print(f"CALLS_PER_ARM_TASK={S1_CALLS_PER_ARM_TASK}")
    print(f"PLANNED_PHYSICAL_CALLS={planned}")
    print("INTERVENTION_START=deterministic_verified_failure")
    print(f"BEST_SINGLE_MODEL={resolved.best_single_model}")
    print(f"REPAIR_MODEL={resolved.repair_model}")
    print("TIER_A_INFERENCE_AUTHORIZED=false")


def _run_mock(output_dir: str | Path, run_id: str) -> int:
    config = _load_config("configs/test3-s1.yaml")
    arms = _mock_arms()
    best = "qwen3.5:9b-q8_0"
    repair = "cogito:3b-v1-preview-llama-q8_0"
    models = {best: MockModelAdapter(best), repair: MockModelAdapter(repair)}
    runtime = run_s1_screen(
        cases=build_holdout_a_r1(),
        arms=arms,
        model_by_name=models,
        best_single_model=best,
        repair_model=repair,
        run_id=run_id,
        exact_budget=80,
    )
    prereg = {
        "status": "MOCK_VALIDATION_ONLY",
        "section": "S1_FIXED_STACK_ORDER",
        "protocol_revision": S1_PROTOCOL_REVISION,
        "holdout": S1_HOLDOUT,
        "exact_budget": 80,
        "arm_count": 4,
        "physical_call_cap_per_arm": 20,
        "matched_tasks": 10,
        "calls_per_arm_task": 2,
        "arms": list(arms),
        "tier_a_inference_authorized": False,
        "predecessor_invalid_run": PREDECESSOR_INVALID_RUN,
        "predecessor_invalidation": PREDECESSOR_INVALIDATION,
    }
    evidence = _assemble_evidence(
        runtime=runtime,
        preregistration=prereg,
        config=config,
        provenance={
            "run_id": run_id,
            "mode": "mock-validation",
            "protocol_revision": S1_PROTOCOL_REVISION,
            "holdout": S1_HOLDOUT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        full_power_clusters=260,
        mock=True,
    )
    if evidence["verdict"].get("protocol_valid_for_primary_claim") is not True:
        raise AssertionError("S1-R1 mock validation failed the intervention-exposure gate")
    Test3S1ArtifactWriter(output_dir).write_all(evidence)
    return 0


def _run_real(args: argparse.Namespace) -> int:
    if not args.authorize_tier_a:
        print("TIER_A_AUTHORIZATION_REQUIRED: pass --authorize-tier-a to permit local physical model calls", file=sys.stderr)
        return 2
    config = _load_config(args.config)
    resolved = load_s1_inputs(args.s0_dir)
    s1 = dict(config["s1"])
    if resolved.exact_budget != int(s1["hard_call_limit"]):
        raise ValueError("S0 S1 budget freeze does not match S1-R1 runtime config")

    cases = build_holdout_a_r1()
    matched = matched_task_limit(resolved.arms, available_cases=len(cases))
    planned = len(resolved.arms) * matched * S1_CALLS_PER_ARM_TASK
    if matched != S1_R1_MATCHED_TASKS or planned != resolved.exact_budget:
        raise ValueError(f"S1-R1 preflight schedule invalid: matched={matched}, planned_calls={planned}")

    settings = dict(s1.get("ollama") or {})
    names = tuple(dict.fromkeys((resolved.best_single_model, resolved.repair_model)))
    base_adapters = {name: _adapter(name, settings) for name in names}
    base_url = str(settings.get("base_url") or "http://127.0.0.1:11434")
    before = _provenance_snapshot(base_url, names)

    progress = InPlaceS1Progress()
    tracker = S1ProgressTracker(
        progress,
        total_tasks=len(resolved.arms) * matched,
        call_budget=resolved.exact_budget,
    )
    adapters = {name: ProgressReportingAdapter(adapter, tracker) for name, adapter in base_adapters.items()}
    try:
        runtime = run_s1_screen(
            cases=cases,
            arms=resolved.arms,
            model_by_name=adapters,
            best_single_model=resolved.best_single_model,
            repair_model=resolved.repair_model,
            run_id=args.run_id,
            exact_budget=resolved.exact_budget,
        )
    except BaseException:
        tracker.finish(mark_current_complete=False)
        raise
    else:
        tracker.finish(mark_current_complete=True)

    if tracker.physical_calls != int(runtime["physical_model_calls"]):
        raise AssertionError(
            "S1 progress physical-call accounting diverged from runtime: "
            f"{tracker.physical_calls} != {runtime['physical_model_calls']}"
        )
    if int(runtime["physical_model_calls"]) != 80 or runtime.get("protocol_valid_for_primary_claim") is not True:
        raise AssertionError("S1-R1 runtime completed without satisfying the exact-80-call protocol gate")

    anomalies: list[dict[str, Any]] = []
    after: dict[str, Any] | None = None
    try:
        after = _provenance_snapshot(base_url, names)
    except Exception as exc:
        anomalies.append({
            "classification": "post_run_model_identity_snapshot_failed",
            "error_class": type(exc).__name__,
            "error": str(exc),
        })
    provenance = {
        "run_id": args.run_id,
        "mode": "tier-a-local",
        "protocol_revision": S1_PROTOCOL_REVISION,
        "execution_holdout": S1_HOLDOUT,
        "source_s0_holdout": resolved.holdout,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "s0_dir": resolved.s0_dir,
        "test2_tier_a_dir": resolved.test2_tier_a_dir,
        "selected_models": list(names),
        "predecessor_invalid_run": PREDECESSOR_INVALID_RUN,
        "predecessor_invalidation": PREDECESSOR_INVALIDATION,
        "ollama_before": before,
        "ollama_after": after,
    }
    evidence = _assemble_evidence(
        runtime=runtime,
        preregistration=_execution_preregistration(resolved, config),
        config=config,
        provenance=provenance,
        full_power_clusters=resolved.full_power_clusters,
        mock=False,
    )
    evidence["instrumentation_anomalies"].extend(anomalies)
    if anomalies:
        evidence["verdict"] = {
            **evidence["verdict"],
            "verdict": "S1_INSTRUMENTATION_WARNING",
            "tier_a_architecture_claim": False,
            "reason": "S1-R1 inference completed but post-run model identity provenance could not be fully verified; evidence retained and architecture claim withheld.",
        }
        evidence["report"] = _report(evidence["verdict"], runtime)
    Test3S1ArtifactWriter(args.output_dir).write_all(evidence)
    print(f"RUN_ID={args.run_id}")
    print(f"PROTOCOL={S1_PROTOCOL_REVISION}")
    print(f"HOLDOUT={S1_HOLDOUT}")
    print(f"PHYSICAL_MODEL_CALLS={runtime['physical_model_calls']}")
    print(f"MATCHED_TASKS={runtime['matched_task_limit']}")
    print(f"PROTOCOL_VALID={str(bool(evidence['verdict'].get('protocol_valid_for_primary_claim'))).lower()}")
    print(f"VERDICT={evidence['verdict']['verdict']}")
    print(f"EVIDENCE_DIR={args.output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m inverted.test3_s1_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    dry = sub.add_parser("dry-plan")
    dry.add_argument("--s0-dir", required=True)
    dry.add_argument("--config", default="configs/test3-s1.yaml")

    mock = sub.add_parser("mock-smoke")
    mock.add_argument("--output-dir", required=True)
    mock.add_argument("--run-id", default="test3-s1-r1-mock")

    run = sub.add_parser("run")
    run.add_argument("--s0-dir", required=True)
    run.add_argument("--config", default="configs/test3-s1.yaml")
    run.add_argument("--output-dir", required=True)
    run.add_argument("--run-id", default="test3-s1-r1-local")
    run.add_argument("--authorize-tier-a", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "dry-plan":
        _load_config(args.config)
        _dry_plan(load_s1_inputs(args.s0_dir))
        return 0
    if args.command == "mock-smoke":
        return _run_mock(args.output_dir, args.run_id)
    if args.command == "run":
        return _run_real(args)
    raise AssertionError(f"unknown S1 command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
