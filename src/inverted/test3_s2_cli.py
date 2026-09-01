from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import httpx
import yaml

from .models import MockModelAdapter, OllamaAdapter
from .test2_provenance import collect_ollama_provenance
from .test3_s2_analysis import derive_s2_verdict, summarize_s2
from .test3_s2_artifacts import Test3S2ArtifactWriter
from .test3_s2_budget import ABSOLUTE_PER_TEST_ACTION_CEILING, CombinedActionBudget
from .test3_s2_cases import S2_HOLDOUT, S2_PERTURBATIONS, S2_PROTOCOL_REVISION, build_holdout_b
from .test3_s2_policy import INTERVENTION_LIBRARY, REAL_ARM_IDS
from .test3_s2_progress import InPlaceS2Progress, ProgressReportingAdapter, S2ProgressTracker
from .test3_s2_runtime import (
    S2_CALLS_PER_ARM_TASK,
    S2_COMBINED_ACTION_BUDGET,
    S2_EXACT_BUDGET,
    S2_LLAMA_MODEL,
    S2_MATCHED_CASES,
    S2_MODEL_NAMES,
    S2_PER_ARM_CALL_CAP,
    S2_PROVENANCE_API_CALL_BUDGET,
    S2_QWEN_MODEL,
    S2_REPAIR_MODEL,
    S2_TRIAL_COUNT,
    run_s2_screen,
)


S2_SPEC = "docs/superpowers/specs/2026-09-01-test3-s2-adaptive-routing-design.md"
S2_PREDECESSOR_RUN = "test3-s1-r3-20260901-154839"
S2_PREDECESSOR_VERDICT = "S1_R3_SCREEN_NON_DECISIVE"


class S2OllamaAdapter(OllamaAdapter):
    """S2-local executor schema covering every legitimate task operation."""

    _EXECUTOR_SCHEMA = {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["set", "resolve", "delete", "grant", "start"]},
                        "path": {"type": "string"},
                        "value": {"type": ["string", "number", "boolean", "object", "array", "null"]},
                    },
                    "required": ["op", "path"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["actions"],
        "additionalProperties": False,
    }


class _BudgetedTransport(httpx.BaseTransport):
    """Count each real provenance HTTP request before it leaves the process."""

    def __init__(self, budget: CombinedActionBudget):
        self._budget = budget
        self._inner = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self._budget.reserve("provenance_api_call")
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def _load_config(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict) or not isinstance(value.get("s2"), dict):
        raise ValueError("Test3 S2 config must contain an s2 mapping")
    s2 = dict(value["s2"])
    expected = {
        "section": "S2_ADAPTIVE_ROUTING",
        "protocol_revision": S2_PROTOCOL_REVISION,
        "holdout": S2_HOLDOUT,
        "hard_call_limit": S2_EXACT_BUDGET,
        "combined_action_budget": S2_COMBINED_ACTION_BUDGET,
        "provenance_api_call_budget": S2_PROVENANCE_API_CALL_BUDGET,
        "absolute_action_ceiling": ABSOLUTE_PER_TEST_ACTION_CEILING,
        "arm_count": len(REAL_ARM_IDS),
        "per_arm_call_cap": S2_PER_ARM_CALL_CAP,
        "matched_cases": S2_MATCHED_CASES,
        "calls_per_arm_task": S2_CALLS_PER_ARM_TASK,
        "execution_mode": "balanced_task_blocks",
        "intervention_start": "deterministic_verified_failure",
        "perturbation_classes": list(S2_PERTURBATIONS),
        "intervention_library": list(INTERVENTION_LIBRARY),
    }
    for key, required in expected.items():
        if s2.get(key) != required:
            raise ValueError(f"S2-R1 config {key} must be exactly {required!r}")
    models = dict(s2.get("models") or {})
    if models != {"qwen": S2_QWEN_MODEL, "repair": S2_REPAIR_MODEL, "llama": S2_LLAMA_MODEL}:
        raise ValueError("S2-R1 config must freeze exactly the selected Qwen, Cogito, and Llama models")
    if s2.get("no_outcome_dependent_early_stopping") is not True:
        raise ValueError("S2-R1 forbids outcome-dependent early stopping")
    adaptive = dict(s2.get("adaptive_signal_rule") or {})
    required_adaptive = {
        "min_net_wins_vs_fixed": 4,
        "min_net_wins_vs_random": 4,
        "min_success_rate_delta_vs_fixed": 0.05,
        "max_catastrophes_added_vs_fixed": 0,
        "min_supported_strata": 3,
        "min_stratum_net_wins": 2,
        "require_lower_oracle_regret": True,
        "require_divergence_exclusion_survival": True,
    }
    if adaptive != required_adaptive:
        raise ValueError("S2-R1 adaptive signal thresholds must remain frozen")
    incremental = dict(s2.get("failure_evidence_incremental_rule") or {})
    if incremental != {"min_net_wins_b2_vs_b1": 3, "max_catastrophes_added_b2_vs_b1": 0}:
        raise ValueError("S2-R1 B2-vs-B1 incremental thresholds must remain frozen")
    harmful = dict(s2.get("harmful_rule") or {})
    if harmful != {
        "max_net_wins_vs_fixed": -4,
        "catastrophe_condition_min_added": 2,
        "catastrophe_condition_require_nonpositive_net_wins": True,
    }:
        raise ValueError("S2-R1 harmful thresholds must remain frozen")
    ollama = dict(s2.get("ollama") or {})
    if int(ollama.get("transport_retries") or 0) != 0:
        raise ValueError("S2-R1 Ollama transport retries must be zero")
    planned_inference = int(s2["matched_cases"]) * int(s2["arm_count"]) * int(s2["calls_per_arm_task"])
    if planned_inference != S2_EXACT_BUDGET or planned_inference != int(s2["hard_call_limit"]):
        raise ValueError("S2-R1 inference schedule must resolve to exactly 720 physical model calls")
    if planned_inference + int(s2["provenance_api_call_budget"]) != int(s2["combined_action_budget"]):
        raise ValueError("S2-R1 combined action budget must cover 720 inference + 12 provenance API calls")
    if int(s2["combined_action_budget"]) > int(s2["absolute_action_ceiling"]):
        raise ValueError("S2-R1 combined action budget exceeds repository absolute ceiling")
    return value


def _policy_snapshot() -> dict[str, Any]:
    return {
        "protocol_revision": S2_PROTOCOL_REVISION,
        "intervention_library": list(INTERVENTION_LIBRARY),
        "arms": {
            "S2-B0": {"router": "fixed", "features": [], "sequence": ["retry_qwen", "repair_cogito"]},
            "S2-B1": {"router": "task_family", "features": ["family"]},
            "S2-B2": {"router": "failure_signature", "features": ["failed_requirement_ids", "failed_requirement_kinds", "failed_count", "failure_signature", "deterministic_success", "catastrophic"]},
            "S2-B3": {"router": "rich_evidence_state", "features": ["family", "complexity", "failed_requirement_ids", "failed_requirement_kinds", "failed_count", "failure_signature", "deterministic_success", "catastrophic", "previous_action", "previous_model", "retry_count", "budget_spent", "budget_remaining"]},
            "S2-B4": {"router": "seeded_random_negative_control", "features": [], "rng": "sha256 outcome-independent frozen seed stream"},
        },
        "forbidden_features": ["target_state", "hidden_gold", "injected_faults", "perturbation_class", "future_outcome", "oracle_selected_action"],
    }


def _policy_hash_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm_id, policy in sorted(dict(snapshot.get("arms") or {}).items()):
        raw = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        rows.append({"arm_id": arm_id, "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "policy": policy})
    return rows


def _adapter(name: str, settings: dict[str, Any]) -> S2OllamaAdapter:
    return S2OllamaAdapter(
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


def _provenance_snapshot(base_url: str, model_names: tuple[str, ...], action_budget: CombinedActionBudget) -> dict[str, Any]:
    snapshot = collect_ollama_provenance(
        base_url,
        model_names,
        transport=_BudgetedTransport(action_budget),
    )
    models = snapshot.get("models") if isinstance(snapshot, dict) else None
    if not isinstance(models, dict) or set(models) != set(model_names):
        raise ValueError("S2 Ollama identity preflight did not resolve exactly the three frozen models")
    for name in model_names:
        row = models.get(name) or {}
        if str(row.get("requested_name") or "") != name or not str(row.get("tag_digest") or ""):
            raise ValueError(f"S2 Ollama identity preflight failed for {name}")
    return snapshot


def _preregistration(*, mock: bool) -> dict[str, Any]:
    return {
        "status": "MOCK_VALIDATION_ONLY" if mock else "FROZEN_TIER_A_EXECUTION",
        "section": "S2_ADAPTIVE_ROUTING",
        "protocol_revision": S2_PROTOCOL_REVISION,
        "holdout": S2_HOLDOUT,
        "spec": S2_SPEC,
        "predecessor_run": S2_PREDECESSOR_RUN,
        "predecessor_verdict": S2_PREDECESSOR_VERDICT,
        "exact_budget": S2_EXACT_BUDGET,
        "combined_action_budget": S2_COMBINED_ACTION_BUDGET,
        "provenance_api_call_budget": S2_PROVENANCE_API_CALL_BUDGET,
        "absolute_action_ceiling": ABSOLUTE_PER_TEST_ACTION_CEILING,
        "arm_count": len(REAL_ARM_IDS),
        "physical_call_cap_per_arm": S2_PER_ARM_CALL_CAP,
        "matched_cases": S2_MATCHED_CASES,
        "calls_per_arm_task": S2_CALLS_PER_ARM_TASK,
        "execution_mode": "balanced_task_blocks",
        "intervention_start": "deterministic_verified_failure",
        "perturbation_classes": list(S2_PERTURBATIONS),
        "intervention_library": list(INTERVENTION_LIBRARY),
        "models": list(S2_MODEL_NAMES),
        "equal_compute": True,
        "terminal_second_call": "shadow_non_mutating",
        "no_outcome_dependent_early_stopping": True,
        "stochastic_divergence_gate": "promotion_must_survive_exclusion",
        "tier_a_inference_authorized": not mock,
    }


def _report(verdict: dict[str, Any], runtime: dict[str, Any], analysis: dict[str, Any]) -> str:
    arm_rates = {str(row.get("arm_id")): float(row.get("success_rate") or 0.0) for row in analysis.get("arm_summaries") or []}
    lines = [
        "VELMA TEST 3 — SECTION 2 S2-R1 ADAPTIVE ROUTING",
        f"RUN_ID={runtime.get('run_id')}",
        f"PROTOCOL={S2_PROTOCOL_REVISION}",
        f"HOLDOUT={S2_HOLDOUT}",
        f"PHYSICAL_MODEL_CALLS={runtime.get('physical_model_calls')}",
        f"COMBINED_EXTERNAL_ACTIONS={(runtime.get('action_budget') or {}).get('combined_used')}",
        f"COMBINED_ACTION_LIMIT={(runtime.get('action_budget') or {}).get('limit')}",
        f"MATCHED_CASES={S2_MATCHED_CASES}",
        f"TRIALS={S2_TRIAL_COUNT}",
        f"PROTOCOL_VALID={str(bool(verdict.get('protocol_valid_for_primary_claim'))).lower()}",
        f"VERDICT={verdict.get('verdict')}",
        f"REASON={verdict.get('reason')}",
        f"STOCHASTIC_DIVERGENCES={len(runtime.get('stochastic_divergence') or [])}",
    ]
    for arm_id in REAL_ARM_IDS:
        lines.append(f"{arm_id}_SUCCESS_RATE={arm_rates.get(arm_id, 0.0):.6f}")
    return "\n".join(lines) + "\n"


def _assemble_evidence(
    *, runtime: dict[str, Any],
    config: dict[str, Any],
    provenance: dict[str, Any],
    mock: bool,
) -> dict[str, Any]:
    analysis = summarize_s2(runtime)
    verdict = derive_s2_verdict(analysis)
    snapshot = _policy_snapshot()
    divergences = list(runtime.get("stochastic_divergence") or [])
    edge_cases: list[dict[str, Any]] = []
    for row in runtime.get("trials") or []:
        if row.get("catastrophic") or not row.get("success"):
            edge_cases.append({
                "arm_id": row.get("arm_id"),
                "task_id": row.get("task_id"),
                "family": row.get("family"),
                "complexity": row.get("complexity"),
                "perturbation_class": row.get("perturbation_class"),
                "success": bool(row.get("success")),
                "catastrophic": bool(row.get("catastrophic")),
                "final_failed_requirements": row.get("final_failed_requirements"),
                "actions_selected": row.get("actions_selected"),
                "models_selected": row.get("models_selected"),
            })
    return {
        **runtime,
        **analysis,
        "preregistration": _preregistration(mock=mock),
        "config": config,
        "provenance": provenance,
        "router_policy_snapshot": snapshot,
        "router_policy_hashes": _policy_hash_rows(snapshot),
        "protocol_failures": list(analysis.get("protocol_failures") or []),
        "edge_cases": edge_cases,
        "instrumentation_anomalies": divergences,
        "verdict": verdict,
        "report": _report(verdict, runtime, analysis),
    }


def _dry_plan(config: dict[str, Any]) -> None:
    s2 = dict(config["s2"])
    cases = build_holdout_b()
    planned = len(cases) * len(REAL_ARM_IDS) * S2_CALLS_PER_ARM_TASK
    print("SECTION=S2_ADAPTIVE_ROUTING")
    print(f"PROTOCOL={S2_PROTOCOL_REVISION}")
    print(f"HOLDOUT={S2_HOLDOUT}")
    print(f"EXACT_BUDGET={int(s2['hard_call_limit'])}")
    print(f"COMBINED_ACTION_BUDGET={int(s2['combined_action_budget'])}")
    print(f"PROVENANCE_API_CALL_BUDGET={int(s2['provenance_api_call_budget'])}")
    print(f"ABSOLUTE_ACTION_CEILING={int(s2['absolute_action_ceiling'])}")
    print(f"ARM_COUNT={len(REAL_ARM_IDS)}")
    print(f"PER_ARM_CALL_CAP={S2_PER_ARM_CALL_CAP}")
    print(f"MATCHED_CASES={len(cases)}")
    print(f"CAUSAL_TWIN_BASE_TASKS={len(cases) // len(S2_PERTURBATIONS)}")
    print(f"PERTURBATION_CLASSES={','.join(S2_PERTURBATIONS)}")
    print(f"CALLS_PER_ARM_TASK={S2_CALLS_PER_ARM_TASK}")
    print(f"PLANNED_PHYSICAL_CALLS={planned}")
    print("EXECUTION_MODE=balanced_task_blocks")
    print(f"QWEN_MODEL={S2_QWEN_MODEL}")
    print(f"REPAIR_MODEL={S2_REPAIR_MODEL}")
    print(f"LLAMA_MODEL={S2_LLAMA_MODEL}")
    print("TIER_A_INFERENCE_AUTHORIZED=false")


def _run_mock(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    progress = InPlaceS2Progress()
    tracker = S2ProgressTracker(progress, total_trials=S2_TRIAL_COUNT, call_budget=S2_EXACT_BUDGET)
    models = {
        name: ProgressReportingAdapter(MockModelAdapter(name), tracker)
        for name in S2_MODEL_NAMES
    }
    try:
        runtime = run_s2_screen(
            cases=build_holdout_b(),
            model_by_name=models,
            run_id=args.run_id,
            exact_budget=S2_EXACT_BUDGET,
        )
    except BaseException:
        tracker.finish(mark_current_complete=False)
        raise
    else:
        tracker.finish(mark_current_complete=True)
    if tracker.physical_calls != int(runtime["physical_model_calls"]):
        raise AssertionError(
            f"S2 mock progress call accounting diverged: {tracker.physical_calls} != {runtime['physical_model_calls']}"
        )
    evidence = _assemble_evidence(
        runtime=runtime,
        config=config,
        provenance={
            "run_id": args.run_id,
            "mode": "mock-validation",
            "protocol_revision": S2_PROTOCOL_REVISION,
            "execution_holdout": S2_HOLDOUT,
            "spec": S2_SPEC,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "selected_models": list(S2_MODEL_NAMES),
            "predecessor_run": S2_PREDECESSOR_RUN,
            "predecessor_verdict": S2_PREDECESSOR_VERDICT,
            "external_provenance_api_calls": 0,
        },
        mock=True,
    )
    if evidence["verdict"].get("protocol_valid_for_primary_claim") is not True:
        raise AssertionError("S2-R1 mock validation failed protocol gates")
    Test3S2ArtifactWriter(args.output_dir).write_all(evidence)
    return 0


def _run_real(args: argparse.Namespace) -> int:
    if not args.authorize_tier_a:
        print("TIER_A_AUTHORIZATION_REQUIRED: pass --authorize-tier-a to permit local physical model calls", file=sys.stderr)
        return 2
    config = _load_config(args.config)
    s2 = dict(config["s2"])
    settings = dict(s2.get("ollama") or {})
    base_url = str(settings.get("base_url") or "http://127.0.0.1:11434")
    base_adapters = {name: _adapter(name, settings) for name in S2_MODEL_NAMES}
    combined = CombinedActionBudget(S2_COMBINED_ACTION_BUDGET)
    before = _provenance_snapshot(base_url, S2_MODEL_NAMES, combined)

    progress = InPlaceS2Progress()
    tracker = S2ProgressTracker(progress, total_trials=S2_TRIAL_COUNT, call_budget=S2_EXACT_BUDGET)
    adapters = {name: ProgressReportingAdapter(adapter, tracker) for name, adapter in base_adapters.items()}
    try:
        runtime = run_s2_screen(
            cases=build_holdout_b(),
            model_by_name=adapters,
            run_id=args.run_id,
            exact_budget=S2_EXACT_BUDGET,
            action_budget=combined,
        )
    except BaseException:
        tracker.finish(mark_current_complete=False)
        raise
    else:
        tracker.finish(mark_current_complete=True)

    if tracker.physical_calls != int(runtime["physical_model_calls"]):
        raise AssertionError(f"S2 progress call accounting diverged: {tracker.physical_calls} != {runtime['physical_model_calls']}")
    anomalies: list[dict[str, Any]] = []
    after: dict[str, Any] | None = None
    try:
        after = _provenance_snapshot(base_url, S2_MODEL_NAMES, combined)
    except Exception as exc:
        anomalies.append({"classification": "post_run_model_identity_snapshot_failed", "error_class": type(exc).__name__, "error": str(exc)})
    runtime["action_budget"] = combined.snapshot()
    provenance_api_calls = int(runtime["action_budget"].get("by_kind", {}).get("provenance_api_call", 0))
    if not anomalies and provenance_api_calls != S2_PROVENANCE_API_CALL_BUDGET:
        anomalies.append({
            "classification": "provenance_api_call_accounting_mismatch",
            "expected": S2_PROVENANCE_API_CALL_BUDGET,
            "actual": provenance_api_calls,
        })

    provenance = {
        "run_id": args.run_id,
        "mode": "tier-a-local",
        "protocol_revision": S2_PROTOCOL_REVISION,
        "execution_holdout": S2_HOLDOUT,
        "execution_mode": "balanced_task_blocks",
        "spec": S2_SPEC,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_models": list(S2_MODEL_NAMES),
        "predecessor_run": S2_PREDECESSOR_RUN,
        "predecessor_verdict": S2_PREDECESSOR_VERDICT,
        "ollama_before": before,
        "ollama_after": after,
        "external_provenance_api_calls": provenance_api_calls,
    }
    evidence = _assemble_evidence(runtime=runtime, config=config, provenance=provenance, mock=False)
    evidence["instrumentation_anomalies"].extend(anomalies)
    if anomalies:
        evidence["verdict"] = {
            **evidence["verdict"],
            "verdict": "S2_INSTRUMENTATION_WARNING",
            "tier_a_architecture_claim": False,
            "reason": "S2 inference completed but provenance instrumentation was incomplete or inconsistent; evidence retained and architecture claim withheld.",
        }
        evidence["report"] = _report(evidence["verdict"], runtime, evidence)
    Test3S2ArtifactWriter(args.output_dir).write_all(evidence)
    print(f"RUN_ID={args.run_id}")
    print(f"PROTOCOL={S2_PROTOCOL_REVISION}")
    print(f"HOLDOUT={S2_HOLDOUT}")
    print(f"PHYSICAL_MODEL_CALLS={runtime['physical_model_calls']}")
    print(f"COMBINED_EXTERNAL_ACTIONS={runtime['action_budget']['combined_used']}")
    print(f"MATCHED_CASES={S2_MATCHED_CASES}")
    print(f"PROTOCOL_VALID={str(bool(evidence['verdict'].get('protocol_valid_for_primary_claim'))).lower()}")
    print(f"VERDICT={evidence['verdict']['verdict']}")
    print(f"EVIDENCE_DIR={args.output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m inverted.test3_s2_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    dry = sub.add_parser("dry-plan")
    dry.add_argument("--config", default="configs/test3-s2.yaml")
    mock = sub.add_parser("mock-run")
    mock.add_argument("--config", default="configs/test3-s2.yaml")
    mock.add_argument("--output-dir", required=True)
    mock.add_argument("--run-id", default="test3-s2-r1-mock")
    run = sub.add_parser("run")
    run.add_argument("--config", default="configs/test3-s2.yaml")
    run.add_argument("--output-dir", required=True)
    run.add_argument("--run-id", default="test3-s2-r1-local")
    run.add_argument("--authorize-tier-a", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "dry-plan":
        _dry_plan(_load_config(args.config))
        return 0
    if args.command == "mock-run":
        return _run_mock(args)
    if args.command == "run":
        return _run_real(args)
    raise AssertionError(f"unknown S2 command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
