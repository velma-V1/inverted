from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Iterable

import yaml

from .test3_s0_analysis import (
    bootstrap_effect_ci,
    build_candidate_s1_preregistration,
    estimate_required_task_clusters,
    pareto_rank_candidates,
    score_fixed_policies,
    score_grouped_policy,
    score_negative_controls,
)
from .test3_s0_artifacts import Test3S0ArtifactWriter
from .test3_s0_counterfactuals import audit_counterfactuals, enumerate_replay_candidates
from .test3_s0_inputs import (
    SourceAvailability,
    load_source_manifest,
    verify_evidence_bundle,
    write_source_manifest,
)
from .test3_s0_normalize import NormalizationResult, normalize_bundle
from .test3_s0_types import CounterfactualStatus, EvidenceSource, TransitionRecord, ZeroModelCallGuard


ALLOWED_VERDICTS = {
    "DISCOVERY_COMPLETE_MODEL_FREE",
    "PARTIAL_INPUT_EVIDENCE",
    "INSTRUMENTATION_FAILURE",
    "SOURCE_INTEGRITY_FAILURE",
}


def load_s0_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError("Test-3 S0 config must be a mapping")
    if value.get("mode") != "model-free":
        raise ValueError("Section 0 mode must be model-free")
    if int(value.get("physical_model_call_ceiling", -1)) != 0:
        raise ValueError("Section 0 physical_model_call_ceiling must be exactly 0")
    if bool(value.get("architecture_claims_authorized", True)):
        raise ValueError("Section 0 architecture_claims_authorized must be false")
    return value


def _manifest_dict(sources: Iterable[EvidenceSource]) -> dict[str, Any]:
    return {
        "schema": "test3-s0-source-manifest-v1",
        "sources": [asdict(source) for source in sources],
    }


def _verify_sources(sources: list[EvidenceSource]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    for source in sources:
        availability = SourceAvailability.from_path(source.path, source.required)
        row: dict[str, Any] = {
            "source_id": source.source_id,
            "source_class": source.source_class,
            "path": source.path,
            "required": source.required,
            "available": availability.available,
            "scientific_blocker": availability.scientific_blocker,
            "integrity_ok": False,
            "claims_complete": source.complete_claim if source.complete_claim is not None else True,
            "git_sha": source.git_sha,
            "run_id": source.run_id,
            "evidence_tier": source.evidence_tier,
        }
        if not availability.available:
            row["errors"] = [availability.reason]
            rows.append(row)
            details[source.source_id] = {"availability": asdict(availability)}
            continue
        verification = verify_evidence_bundle(
            source.path,
            claims_complete=bool(source.complete_claim if source.complete_claim is not None else True),
        )
        row.update({
            "integrity_ok": verification.integrity_ok,
            "sha_inventory_present": verification.sha_inventory_present,
            "hashed_file_count": len(verification.hashed_files),
            "unhashed_extra_count": len(verification.unhashed_extras),
            "unhashed_extras": verification.unhashed_extras,
            "missing_hashed_files": verification.missing_hashed_files,
            "mismatched_hashes": verification.mismatched_hashes,
            "byte_mismatches": verification.byte_mismatches,
            "errors": verification.errors,
            "observed_run_id": verification.metadata.get("run_id"),
            "observed_git_sha": verification.metadata.get("git_sha"),
            "observed_physical_model_calls": verification.metadata.get("physical_model_calls"),
        })
        rows.append(row)
        details[source.source_id] = verification.to_dict()
    return rows, details


def _required_source_status(config: dict[str, Any], sources: list[EvidenceSource], integrity_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required_classes = {str(item) for item in config.get("required_source_classes", [])}
    by_class: dict[str, list[dict[str, Any]]] = {}
    for row in integrity_rows:
        by_class.setdefault(str(row.get("source_class")), []).append(row)
    missing = sorted(cls for cls in required_classes if not any(bool(row.get("available")) for row in by_class.get(cls, [])))
    failed = sorted(
        cls for cls in required_classes
        if any(bool(row.get("available")) for row in by_class.get(cls, []))
        and not any(bool(row.get("integrity_ok")) for row in by_class.get(cls, []))
    )
    return {
        "required_classes": sorted(required_classes),
        "missing_required_classes": missing,
        "integrity_failed_required_classes": failed,
        "all_required_present": not missing,
        "all_required_verified": not missing and not failed,
    }


def _empty_evidence(
    config: dict[str, Any],
    sources: list[EvidenceSource],
    integrity_rows: list[dict[str, Any]],
    source_details: dict[str, Any],
    verdict: str,
    reason: str,
) -> dict[str, Any]:
    if verdict not in ALLOWED_VERDICTS:
        raise ValueError(verdict)
    anomalies = []
    for row in integrity_rows:
        for error in row.get("errors") or []:
            anomalies.append({"source_id": row.get("source_id"), "kind": "source_integrity", "detail": error})
        for extra in row.get("unhashed_extras") or []:
            anomalies.append({"source_id": row.get("source_id"), "kind": "unhashed_extra", "detail": extra})
    return {
        "preregistration": {
            "section": "S0",
            "status": "FROZEN_MODEL_FREE_SECTION",
            "tier_a_inference_authorized": False,
            "physical_model_call_ceiling": 0,
            "architecture_claims_authorized": False,
        },
        "config": config,
        "provenance": {
            "source_verification": source_details,
            "execution_mode": "model-free",
            "physical_model_calls": 0,
        },
        "source_manifest": _manifest_dict(sources),
        "source_integrity": integrity_rows,
        "model_calls": [],
        "events": [],
        "trials": [],
        "validator_results": [],
        "failures": [],
        "wins": [],
        "losses": [],
        "transitions": [],
        "counterfactuals": [],
        "costs": [],
        "latency": [],
        "tokens": [],
        "cache": [],
        "failure_atlas": {},
        "effect_sizes": {},
        "normalization_coverage": [],
        "normalization_errors": [],
        "fixed_policy_candidates": [],
        "adaptive_policy_candidates": [],
        "control_results": [],
        "pareto_frontier": [],
        "unresolved_causal_questions": [],
        "requires_new_inference": [],
        "invalid_counterfactuals": [],
        "power_variance": {"status": "NOT_ESTIMATED"},
        "candidate_section1_preregistration": build_candidate_s1_preregistration({"status": "INSUFFICIENT_VARIANCE_EVIDENCE", "recommended_clusters": None}),
        "instrumentation_anomalies": anomalies,
        "metadata_catalog": [],
        "field_provenance": [],
        "source_file_inventory": [],
        "decision_trace": [],
        "unknown_fields": [],
        "edge_cases": [],
        "data_quality": {},
        "verdict": {
            "verdict": verdict,
            "reason": reason,
            "physical_model_calls": 0,
            "architecture_claims_authorized": False,
        },
        "report": (
            "VELMA TEST 3 — SECTION 0\n"
            "==========================\n"
            f"Verdict: {verdict}\n"
            f"Reason: {reason}\n"
            "Physical model calls: 0\n"
            "Architecture claims authorized: false\n"
        ),
    }


def _transition_analysis_row(transition: TransitionRecord) -> dict[str, Any]:
    outcome = transition.state_after
    state = transition.state_before
    return {
        "task_id": state.task_id,
        "causal_twin_id": state.causal_twin_id,
        "task_family": state.task_family,
        "complexity": state.complexity,
        "representation": state.representation,
        "failure_signature": state.failure_signature or outcome.failure_signature,
        "failure_class": state.failure_class or outcome.failure_class,
        "action": transition.action.component,
        "model": transition.action.model,
        "role": transition.action.role,
        "verifier": transition.action.verifier,
        "success": outcome.success,
        "catastrophic": outcome.catastrophic,
        "calls": outcome.physical_calls_delta,
        "tokens": outcome.tokens_delta,
        "latency_ms": outcome.elapsed_ms_delta,
        "source_id": transition.source_id,
        "transition_id": transition.transition_id,
    }


def _flatten_field_provenance(transitions: Iterable[TransitionRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for transition in transitions:
        for feature in transition.state_before.feature_provenance:
            rows.append({
                "transition_id": transition.transition_id,
                "task_id": transition.state_before.task_id,
                **asdict(feature),
            })
    return rows


def _metadata_catalog(results: Iterable[NormalizationResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for item in result.metadata_records:
            value = item.get("value")
            rows.append({
                "source_id": item.get("source_id"),
                "source_file": item.get("source_file"),
                "value_type": type(value).__name__,
                "top_level_keys": sorted(value.keys()) if isinstance(value, dict) else [],
                "item_count": len(value) if isinstance(value, (dict, list)) else None,
            })
    return rows


def _build_failure_atlas(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signatures = Counter(str(row.get("failure_signature") or "UNKNOWN") for row in rows if row.get("success") is not True)
    classes = Counter(str(row.get("failure_class") or "UNKNOWN") for row in rows if row.get("success") is not True)
    actions = Counter(str(row.get("action") or "unknown") for row in rows)
    edge_cases = [
        {"kind": "rare_failure_signature", "failure_signature": key, "count": count}
        for key, count in signatures.items() if count <= 2
    ]
    return {
        "failure_signatures": dict(signatures.most_common()),
        "failure_classes": dict(classes.most_common()),
        "actions": dict(actions.most_common()),
        "total_rows": len(rows),
        "rare_signature_count": len(edge_cases),
    }, edge_cases


def _power_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = [row for row in rows if isinstance(row.get("success"), bool)]
    if not known:
        return []
    baseline = sum(int(row["success"]) for row in known) / len(known)
    return [
        {
            "cluster_id": row.get("causal_twin_id") or row.get("task_id"),
            "effect": int(bool(row["success"])) - baseline,
        }
        for row in known
    ]


def _run_discovery(config: dict[str, Any], sources: list[EvidenceSource], integrity_rows: list[dict[str, Any]], source_details: dict[str, Any]) -> dict[str, Any]:
    guard = ZeroModelCallGuard()
    results: list[NormalizationResult] = []
    transitions: list[TransitionRecord] = []
    for source in sources:
        result = normalize_bundle(source.source_id, source.source_class, source.path)
        results.append(result)
        transitions.extend(result.transitions)

    coverage = [row for result in results for row in result.coverage]
    normalization_errors = [row for result in results for row in result.errors]
    source_file_inventory = [row for result in results for row in result.source_file_inventory]
    comparisons = [row for result in results for row in result.comparisons]
    analysis_rows = [_transition_analysis_row(transition) for transition in transitions]

    counterfactuals = enumerate_replay_candidates(transitions)
    counterfactual_audit = audit_counterfactuals(counterfactuals)
    fixed = score_fixed_policies(analysis_rows)
    adaptive = score_grouped_policy(analysis_rows, folds=5) if analysis_rows else {
        "folds": 5, "rows": 0, "replayable_rows": 0, "coverage": 0.0, "verified_success_rate": None, "fold_results": []
    }
    controls = score_negative_controls(analysis_rows, seed=20260901)
    pareto = pareto_rank_candidates(fixed)

    power_input = _power_rows(analysis_rows)
    power_cfg = dict(config.get("power") or {})
    bootstrap = bootstrap_effect_ci(
        power_input,
        iterations=int(power_cfg.get("bootstrap_iterations", 20000)),
        seed=int(power_cfg.get("seed", 20260901)),
        alpha=float(power_cfg.get("candidate_alpha", 0.05)),
    )
    power = estimate_required_task_clusters(
        power_input,
        target_effect=float(power_cfg.get("target_effect", 0.03)),
        alpha=float(power_cfg.get("candidate_alpha", 0.05)),
        target_power=float(power_cfg.get("target_power", 0.80)),
    )
    power["bootstrap"] = bootstrap
    candidate_s1 = build_candidate_s1_preregistration(power)

    failure_atlas, rare_edges = _build_failure_atlas(analysis_rows)
    invalid = [row for row in counterfactuals if row.status is CounterfactualStatus.INVALID_COUNTERFACTUAL]
    requires = [row for row in counterfactuals if row.status is CounterfactualStatus.REQUIRES_NEW_INFERENCE]

    unresolved: list[dict[str, Any]] = []
    if requires:
        unresolved.append({"question": "Which queued policy mutations survive fresh inference?", "count": len(requires), "reason": "requires new model output"})
    if any(row.get("fully_costed") is False for row in fixed):
        unresolved.append({"question": "How does the ranking change with complete token/latency cost telemetry?", "count": sum(row.get("fully_costed") is False for row in fixed), "reason": "historical costs missing"})
    if normalization_errors:
        unresolved.append({"question": "Do malformed historical records change policy ranking after instrumentation repair?", "count": len(normalization_errors), "reason": "normalization errors retained"})

    anomalies: list[dict[str, Any]] = []
    for error in normalization_errors:
        anomalies.append({"kind": "normalization_error", **error})
    for row in integrity_rows:
        for extra in row.get("unhashed_extras") or []:
            anomalies.append({"kind": "unhashed_extra", "source_id": row.get("source_id"), "detail": extra})
    for transition in transitions:
        for anomaly in transition.anomalies:
            anomalies.append({"kind": "historical_transition_anomaly", "transition_id": transition.transition_id, "detail": anomaly})

    unknown_fields: list[dict[str, Any]] = []
    for row in coverage:
        for field_name in row.get("unknown_fields") or []:
            unknown_fields.append({"source_id": row.get("source_id"), "path": row.get("path"), "field": field_name, "record_type": row.get("record_type")})

    events = [
        {
            "transition_id": transition.transition_id,
            "source_id": transition.source_id,
            "task_id": transition.state_before.task_id,
            "action": transition.action.component,
            "success": transition.state_after.success,
            "anomalies": transition.anomalies,
            "raw_record_hash": transition.raw_record_hash,
            "metadata": transition.metadata,
        }
        for transition in transitions
    ]
    model_calls = [
        dict(transition.metadata.get("raw_record") or {})
        for transition in transitions if transition.source_record_type == "model_calls.jsonl"
    ]
    failures = [row for row in analysis_rows if row.get("success") is False]
    wins = [row for row in analysis_rows if row.get("success") is True]
    losses = [row for row in analysis_rows if row.get("success") is False]

    verdict = "INSTRUMENTATION_FAILURE" if normalization_errors else "DISCOVERY_COMPLETE_MODEL_FREE"
    reason = (
        f"S0 normalized {len(transitions)} transitions but retained {len(normalization_errors)} normalization errors; architecture claims remain unauthorized."
        if normalization_errors else
        f"S0 model-free discovery completed over {len(transitions)} normalized transitions with {len(counterfactuals)} audited counterfactuals."
    )

    return {
        "preregistration": {
            "section": "S0",
            "status": "FROZEN_MODEL_FREE_SECTION",
            "tier_a_inference_authorized": False,
            "physical_model_call_ceiling": 0,
            "architecture_claims_authorized": False,
            "counterfactual_statuses": [status.value for status in CounterfactualStatus],
        },
        "config": config,
        "provenance": {
            "source_verification": source_details,
            "execution_mode": "model-free",
            "physical_model_calls": guard.physical_calls,
            "attempted_model_calls": guard.attempted_calls,
        },
        "source_manifest": _manifest_dict(sources),
        "source_integrity": integrity_rows,
        "model_calls": model_calls,
        "events": events,
        "trials": analysis_rows,
        "validator_results": [],
        "failures": failures,
        "wins": wins,
        "losses": losses,
        "transitions": transitions,
        "counterfactuals": counterfactuals,
        "costs": [{"task_id": row.get("task_id"), "transition_id": row.get("transition_id"), "physical_calls": row.get("calls"), "fully_costed": all(row.get(k) is not None for k in ("calls", "tokens", "latency_ms"))} for row in analysis_rows],
        "latency": [{"task_id": row.get("task_id"), "transition_id": row.get("transition_id"), "elapsed_ms": row.get("latency_ms")} for row in analysis_rows],
        "tokens": [{"task_id": row.get("task_id"), "transition_id": row.get("transition_id"), "tokens": row.get("tokens")} for row in analysis_rows],
        "cache": [{"task_id": transition.state_before.task_id, "transition_id": transition.transition_id, "cache_hit": transition.state_after.cache_hit, "cache_hits_before": transition.state_before.cache_hits, "cache_misses_before": transition.state_before.cache_misses} for transition in transitions],
        "failure_atlas": failure_atlas,
        "effect_sizes": {
            "fixed_policy_range": (
                max((row.get("verified_success_rate") for row in fixed if row.get("verified_success_rate") is not None), default=None),
                min((row.get("verified_success_rate") for row in fixed if row.get("verified_success_rate") is not None), default=None),
            ),
            "adaptive_verified_success_rate": adaptive.get("verified_success_rate"),
            "counterfactual_status_counts": counterfactual_audit.get("counts"),
        },
        "normalization_coverage": coverage,
        "normalization_errors": normalization_errors,
        "fixed_policy_candidates": fixed,
        "adaptive_policy_candidates": [adaptive] + list(adaptive.get("fold_results") or []),
        "control_results": controls,
        "pareto_frontier": pareto,
        "unresolved_causal_questions": unresolved,
        "requires_new_inference": requires,
        "invalid_counterfactuals": invalid,
        "power_variance": power,
        "candidate_section1_preregistration": candidate_s1,
        "instrumentation_anomalies": anomalies,
        "metadata_catalog": _metadata_catalog(results),
        "field_provenance": _flatten_field_provenance(transitions),
        "source_file_inventory": source_file_inventory,
        "decision_trace": [{"counterfactual_id": row.counterfactual_id, "status": row.status.value, "reason": row.reason, "source_transition_ids": row.source_transition_ids} for row in counterfactuals],
        "unknown_fields": unknown_fields,
        "edge_cases": rare_edges + [{"kind": "comparison_evidence", "source_file": row.get("source_file"), "record_type": row.get("record_type")} for row in comparisons[:1000]],
        "data_quality": {},
        "verdict": {
            "verdict": verdict,
            "reason": reason,
            "physical_model_calls": guard.physical_calls,
            "attempted_model_calls": guard.attempted_calls,
            "architecture_claims_authorized": False,
        },
        "report": (
            "VELMA TEST 3 — SECTION 0 CAUSAL DISCOVERY\n"
            "===========================================\n"
            f"Verdict: {verdict}\n"
            f"Reason: {reason}\n"
            f"Normalized transitions: {len(transitions)}\n"
            f"Counterfactuals audited: {len(counterfactuals)}\n"
            f"CAUSAL_REPLAY: {counterfactual_audit['counts']['CAUSAL_REPLAY']}\n"
            f"REQUIRES_NEW_INFERENCE: {counterfactual_audit['counts']['REQUIRES_NEW_INFERENCE']}\n"
            f"INVALID_COUNTERFACTUAL: {counterfactual_audit['counts']['INVALID_COUNTERFACTUAL']}\n"
            f"Normalization errors retained: {len(normalization_errors)}\n"
            f"Instrumentation anomalies retained: {len(anomalies)}\n"
            "Physical model calls: 0\n"
            "Architecture claims authorized: false\n"
        ),
    }


def _write_packet(output_dir: str | Path, evidence: dict[str, Any]) -> None:
    Test3S0ArtifactWriter(output_dir).write_all(evidence)


def _cmd_build_manifest(args: argparse.Namespace) -> int:
    sources: list[EvidenceSource] = []
    for required, groups in ((True, args.source or []), (False, args.optional_source or [])):
        for source_id, source_class, raw_path in groups:
            path = Path(raw_path)
            verification = verify_evidence_bundle(path, claims_complete=True) if path.is_dir() else None
            metadata = verification.metadata if verification else {}
            sources.append(EvidenceSource(
                source_id=source_id,
                source_class=source_class,
                path=str(path),
                required=required,
                bundle_sha256=(metadata.get("inventory_sha256") if verification else None),
                git_sha=metadata.get("git_sha"),
                run_id=metadata.get("run_id"),
                evidence_tier=("tier_a" if source_class == "test2_tier_a" else "historical"),
                complete_claim=True,
                metadata={
                    "physical_model_calls": metadata.get("physical_model_calls"),
                    "mode": metadata.get("mode"),
                    "file_count": metadata.get("file_count"),
                },
            ))
    write_source_manifest(args.output, sources)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    config = load_s0_config(args.config)
    sources = load_source_manifest(args.manifest)
    integrity_rows, details = _verify_sources(sources)
    status = _required_source_status(config, sources, integrity_rows)
    reason = (
        "Instrument validation only: required scientific inputs are incomplete. "
        f"Missing={status['missing_required_classes']} integrity_failed={status['integrity_failed_required_classes']}."
    )
    evidence = _empty_evidence(config, sources, integrity_rows, details, "PARTIAL_INPUT_EVIDENCE", reason)
    evidence["provenance"]["required_source_status"] = status
    _write_packet(args.output_dir, evidence)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config = load_s0_config(args.config)
    sources = load_source_manifest(args.manifest)
    integrity_rows, details = _verify_sources(sources)
    status = _required_source_status(config, sources, integrity_rows)
    if status["missing_required_classes"]:
        evidence = _empty_evidence(
            config, sources, integrity_rows, details,
            "PARTIAL_INPUT_EVIDENCE",
            f"Scientific S0 blocked: missing required source classes {status['missing_required_classes']}",
        )
        evidence["provenance"]["required_source_status"] = status
        _write_packet(args.output_dir, evidence)
        return 2
    if status["integrity_failed_required_classes"]:
        evidence = _empty_evidence(
            config, sources, integrity_rows, details,
            "SOURCE_INTEGRITY_FAILURE",
            f"Scientific S0 blocked: source integrity failed for {status['integrity_failed_required_classes']}",
        )
        evidence["provenance"]["required_source_status"] = status
        _write_packet(args.output_dir, evidence)
        return 3
    evidence = _run_discovery(config, sources, integrity_rows, details)
    evidence["provenance"]["required_source_status"] = status
    _write_packet(args.output_dir, evidence)
    return 4 if evidence["verdict"]["verdict"] == "INSTRUMENTATION_FAILURE" else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VELMA Test-3 Section-0 model-free causal discovery")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("build-manifest", help="build an immutable source manifest")
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--source", nargs=3, action="append", metavar=("ID", "CLASS", "PATH"))
    manifest.add_argument("--optional-source", nargs=3, action="append", metavar=("ID", "CLASS", "PATH"))
    manifest.set_defaults(func=_cmd_build_manifest)

    validate = sub.add_parser("validate-instrument", help="validate the S0 instrument with partial inputs allowed")
    validate.add_argument("--config", required=True)
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--output-dir", required=True)
    validate.set_defaults(func=_cmd_validate)

    run = sub.add_parser("run", help="run scientific S0; all required evidence must be present and verified")
    run.add_argument("--config", required=True)
    run.add_argument("--manifest", required=True)
    run.add_argument("--output-dir", required=True)
    run.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
