"""Zero-call CLI adapter for V3 Stage-9 fine-tuning qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .causal_store import CausalEvidenceStore
from .compilation_eligibility import CompilationEligibilityScanner
from .compilation_store import CompilationEvidenceStore
from .fine_tuning_eligibility import FineTuningEligibilityScanner, plan_eligible_fine_tuning
from .fine_tuning_store import FineTuningEvidenceStore
from .mutation_store import MutationEvidenceStore
from .replay_store import ReplayStore
from .surface_store import SurfaceEvidenceStore
from .tomography_store import TomographyEvidenceStore


FINE_TUNING_COMMANDS = frozenset({
    "scan-fine-tuning-eligibility",
    "plan-fine-tuning",
    "show-fine-tuning-candidate",
    "show-fine-tuning-qualification",
    "export-fine-tuning-dataset",
})


def _add_roots(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--replay-root", required=True)
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--surface-root", required=True)
    parser.add_argument("--mutation-root", required=True)
    parser.add_argument("--tomography-root", required=True)
    parser.add_argument("--compilation-root", required=True)
    parser.add_argument("--fine-tuning-root", required=True)


def add_fine_tuning_parsers(sub: argparse._SubParsersAction) -> None:
    scan = sub.add_parser("scan-fine-tuning-eligibility"); _add_roots(scan)
    plan = sub.add_parser("plan-fine-tuning"); _add_roots(plan)
    selector = plan.add_mutually_exclusive_group(required=True)
    selector.add_argument("--candidate-id"); selector.add_argument("--auto-eligible", action="store_true")
    show_candidate = sub.add_parser("show-fine-tuning-candidate"); _add_roots(show_candidate); show_candidate.add_argument("--candidate-id", required=True)
    show_qualification = sub.add_parser("show-fine-tuning-qualification"); _add_roots(show_qualification); show_qualification.add_argument("--qualification-id", required=True)
    export = sub.add_parser("export-fine-tuning-dataset"); _add_roots(export); export.add_argument("--candidate-id", required=True); export.add_argument("--output", required=True)


def _stores(args: argparse.Namespace, replay: ReplayStore):
    causal = CausalEvidenceStore(Path(args.causal_root), replay_store=replay)
    surface = SurfaceEvidenceStore(Path(args.surface_root), replay_store=replay, causal_store=causal)
    mutation = MutationEvidenceStore(Path(args.mutation_root), replay_store=replay, surface_store=surface)
    tomography = TomographyEvidenceStore(Path(args.tomography_root))
    compilation = CompilationEvidenceStore(Path(args.compilation_root), replay_store=replay, mutation_store=mutation, causal_store=causal)
    compilation_scanner = CompilationEligibilityScanner(
        replay_store=replay, mutation_store=mutation, compilation_store=compilation, tomography_store=tomography
    )
    fine_tuning = FineTuningEvidenceStore(Path(args.fine_tuning_root))
    scanner = FineTuningEligibilityScanner(compilation_scanner=compilation_scanner, qualification_store=fine_tuning)
    return fine_tuning, scanner


def _candidate_payload(x) -> dict[str, Any]:
    return {
        "candidate_id": x.candidate_id, "stage8_candidate_id": x.stage8_candidate_id, "mechanism_id": x.mechanism_id,
        "failure_snapshot_ids": list(x.failure_snapshot_ids), "generalization_evidence_refs": list(x.generalization_evidence_refs),
        "tomography_assessment_refs": list(x.tomography_assessment_refs), "cheaper_owner_exclusions": dict(x.cheaper_owner_exclusions),
        "trigger_contract": dict(x.trigger_contract), "allowed_region": x.allowed_region,
        "negative_transfer_boundary": list(x.negative_transfer_boundary), "source_hashes": dict(x.source_hashes),
        "partition": x.partition.value, "base_model_profile_id": x.base_model_profile_id,
        "regression_evidence_refs": list(x.regression_evidence_refs), "model_internal_residual": x.model_internal_residual,
        "generalization_complete": x.generalization_complete, "cheaper_owners_resolved": x.cheaper_owners_resolved,
        "decision_id": x.decision_id,
    }


def _qualification_payload(x) -> dict[str, Any]:
    return {
        "qualification_id": x.qualification_id, "candidate_id": x.candidate_id, "disposition": x.disposition.value,
        "evidence_refs": list(x.evidence_refs), "dataset_id": x.dataset_id, "unresolved_risks": list(x.unresolved_risks),
        "route": x.route, "training_completed": x.training_completed, "certified": x.certified,
        "deployment_allowed": x.deployment_allowed, "stage11_confirmation_required": x.stage11_confirmation_required,
        "decision_id": x.decision_id,
    }


def _dataset_payload(x) -> dict[str, Any]:
    return {
        "MODEL_CALLS": 0, "dataset_id": x.dataset_id, "dataset_hash": x.dataset_hash, "candidate_id": x.candidate_id,
        "train_example_ids": list(x.train_example_ids), "eval_example_ids": list(x.eval_example_ids),
        "examples": [{
            "example_id": e.example_id, "failure_snapshot_id": e.failure_snapshot_id,
            "replay_evidence_refs": list(e.replay_evidence_refs), "model_visible_input_ref": e.model_visible_input_ref,
            "model_visible_input_hash": e.model_visible_input_hash, "observable_target_ref": e.observable_target_ref,
            "observable_target_hash": e.observable_target_hash, "target_type": e.target_type, "role": e.role.value,
            "partition": e.partition.value, "base_model_profile_id": e.base_model_profile_id,
        } for e in x.examples],
        "regression_evidence_refs": list(x.regression_evidence_refs), "negative_transfer_refs": list(x.negative_transfer_refs),
        "training_authorized": False, "certified": False, "deployment_allowed": False,
    }


def handle_fine_tuning_command(replay: ReplayStore, args: argparse.Namespace) -> dict[str, Any]:
    if args.command not in FINE_TUNING_COMMANDS:
        raise ValueError("unsupported Stage-9 CLI command")
    store, scanner = _stores(args, replay)
    if args.command == "scan-fine-tuning-eligibility":
        return {"MODEL_CALLS": 0, "status": "FINE_TUNING_ELIGIBILITY_SCAN", "rows": [row.to_payload() for row in scanner.scan()]}
    if args.command == "plan-fine-tuning":
        boundary = plan_eligible_fine_tuning(scanner)
        if getattr(args, "auto_eligible", False):
            return boundary
        candidate_id = args.candidate_id
        stored = [x for x in store.candidates() if x.candidate_id == candidate_id]
        scanned = [row.candidate for row in scanner.scan() if row.candidate is not None and row.candidate.candidate_id == candidate_id]
        matches = stored or scanned
        if len(matches) != 1:
            raise KeyError(candidate_id)
        return {"MODEL_CALLS": 0, "status": "CANDIDATE_REQUIRES_REGISTERED_LEAKAGE_SAFE_DATASET", "candidate": _candidate_payload(matches[0])}
    if args.command == "show-fine-tuning-candidate":
        return {"MODEL_CALLS": 0, "candidate": _candidate_payload(store.get_candidate(args.candidate_id)), "fine_tuning_store_valid": store.validate().ok}
    if args.command == "show-fine-tuning-qualification":
        return {"MODEL_CALLS": 0, "qualification": _qualification_payload(store.get_qualification(args.qualification_id)), "fine_tuning_store_valid": store.validate().ok}
    matches = [x for x in store.datasets() if x.candidate_id == args.candidate_id]
    if len(matches) != 1:
        raise KeyError(args.candidate_id)
    payload = _dataset_payload(matches[0])
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"MODEL_CALLS": 0, "status": "FINE_TUNING_DATASET_EXPORTED", "dataset_id": matches[0].dataset_id, "dataset_hash": matches[0].dataset_hash, "output": str(output)}
