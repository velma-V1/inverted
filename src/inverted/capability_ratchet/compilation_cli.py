"""Zero-call CLI adapter for V3 Stage-8 capability compilation queries."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .causal_store import CausalEvidenceStore
from .compilation_core import CompilationCandidate, CompilationPlan, CompiledCapability
from .compilation_eligibility import CompilationEligibilityScanner, plan_eligible_compilation
from .compilation_planner import CompilationPlanner
from .compilation_store import CompilationEvidenceStore
from .mutation_store import MutationEvidenceStore
from .replay_store import ReplayStore
from .surface_store import SurfaceEvidenceStore
from .tomography_store import TomographyEvidenceStore


COMPILATION_COMMANDS = frozenset({
    "scan-compilation-eligibility",
    "plan-compilation",
    "show-compiled-capability",
    "export-compiled-capabilities",
})


def _add_roots(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--replay-root", required=True)
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--surface-root", required=True)
    parser.add_argument("--mutation-root", required=True)
    parser.add_argument("--tomography-root", required=True)
    parser.add_argument("--compilation-root", required=True)


def add_compilation_parsers(sub: argparse._SubParsersAction) -> None:
    """Register Stage-8 query/planning/export surfaces; never execution."""

    scan = sub.add_parser("scan-compilation-eligibility")
    _add_roots(scan)

    plan = sub.add_parser("plan-compilation")
    _add_roots(plan)
    selector = plan.add_mutually_exclusive_group(required=True)
    selector.add_argument("--candidate-id")
    selector.add_argument("--auto-eligible", action="store_true")

    show = sub.add_parser("show-compiled-capability")
    _add_roots(show)
    show.add_argument("--capability-id", required=True)

    export = sub.add_parser("export-compiled-capabilities")
    _add_roots(export)
    export.add_argument("--output", required=True)


def _plan_payload(plan: CompilationPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "candidate_id": plan.candidate_id,
        "selected_kind": plan.selected_kind.value,
        "rejected_cheaper_kinds": dict(plan.rejected_cheaper_kinds),
        "evidence_refs": list(plan.evidence_refs),
        "projected_model_calls": plan.projected_model_calls,
        "expected_disposition": plan.expected_disposition.value,
    }


def _capability_payload(value: CompiledCapability) -> dict[str, Any]:
    return {
        "capability_id": value.capability_id,
        "capability_key": value.capability_key,
        "candidate_id": value.candidate_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "mechanism_id": value.mechanism_id,
        "generalization_profile_id": value.generalization_profile_id,
        "prior_generalized_evidence_ref": value.prior_generalized_evidence_ref,
        "selected_kind": value.selected_kind.value,
        "version": value.version,
        "previous_capability_id": value.previous_capability_id,
        "disposition": value.disposition.value,
        "trigger_contract": dict(value.trigger_contract),
        "compiled_payload": dict(value.compiled_payload),
        "verifier_contract": dict(value.verifier_contract),
        "negative_transfer_boundary": list(value.negative_transfer_boundary),
        "tested_region": value.tested_region,
        "evidence_refs": list(value.evidence_refs),
        "source_hashes": dict(value.source_hashes),
        "rollback_action": value.rollback_action,
        "partition": value.partition.value,
        "handoff": value.handoff,
        "deployment_allowed": value.deployment_allowed,
        "fresh_validation_required": value.fresh_validation_required,
    }


def _stores(args: argparse.Namespace, replay: ReplayStore):
    """Construct only deterministic evidence stores; no model/tool/replay executor."""

    causal = CausalEvidenceStore(Path(args.causal_root), replay_store=replay)
    surface = SurfaceEvidenceStore(
        Path(args.surface_root), replay_store=replay, causal_store=causal
    )
    mutation = MutationEvidenceStore(
        Path(args.mutation_root), replay_store=replay, surface_store=surface
    )
    tomography = TomographyEvidenceStore(Path(args.tomography_root))
    compilation = CompilationEvidenceStore(
        Path(args.compilation_root),
        replay_store=replay,
        mutation_store=mutation,
        causal_store=causal,
    )
    scanner = CompilationEligibilityScanner(
        replay_store=replay,
        mutation_store=mutation,
        compilation_store=compilation,
        tomography_store=tomography,
    )
    return compilation, scanner


def _candidate_by_id(
    candidate_id: str,
    *,
    compilation: CompilationEvidenceStore,
    scanner: CompilationEligibilityScanner,
) -> CompilationCandidate:
    stored = tuple(item for item in compilation.candidates() if item.candidate_id == candidate_id)
    if len(stored) == 1:
        return stored[0]
    if len(stored) > 1:
        raise ValueError("candidate ID is duplicated in compilation store")
    scanned = tuple(
        row.candidate
        for row in scanner.scan()
        if row.candidate is not None and row.candidate.candidate_id == candidate_id
    )
    if len(scanned) != 1:
        raise KeyError(candidate_id)
    return scanned[0]


def handle_compilation_command(
    replay: ReplayStore,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Execute a safe Stage-8 query/plan/export command with MODEL_CALLS=0."""

    if args.command not in COMPILATION_COMMANDS:
        raise ValueError("unsupported compilation CLI command")
    compilation, scanner = _stores(args, replay)

    if args.command == "scan-compilation-eligibility":
        rows = scanner.scan()
        return {
            "MODEL_CALLS": 0,
            "status": "COMPILATION_ELIGIBILITY_SCAN",
            "rows": [row.to_payload() for row in rows],
        }

    if args.command == "plan-compilation":
        planner = CompilationPlanner()
        if getattr(args, "auto_eligible", False):
            boundary = plan_eligible_compilation(scanner)
            candidates = tuple(
                row.candidate
                for row in scanner.scan()
                if row.candidate is not None
            )
            return {
                **boundary,
                "plans": [_plan_payload(planner.plan(item)) for item in candidates],
            }
        candidate = _candidate_by_id(
            args.candidate_id, compilation=compilation, scanner=scanner
        )
        return {"MODEL_CALLS": 0, "plan": _plan_payload(planner.plan(candidate))}

    if args.command == "show-compiled-capability":
        capability = compilation.get_capability(args.capability_id)
        return {
            "MODEL_CALLS": 0,
            "capability": _capability_payload(capability),
            "compilation_store_valid": compilation.validate().ok,
        }

    return compilation.export_catalog(Path(args.output))
