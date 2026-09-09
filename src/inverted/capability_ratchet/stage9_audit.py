"""Permanent scientific omission audit for V3 Stage 9.

This module is called by the repository-wide replay-foundation audit.  It is
kept separate so the inherited Stage-5/6/7/8 audit remains readable while
Stage-9's fine-tuning qualification boundary is checked independently.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

import inverted.capability_ratchet as cr
from .core import Partition, PromotionEvent, PromotionState
from .fine_tuning_cli import FINE_TUNING_COMMANDS, add_fine_tuning_parsers
from .fine_tuning_core import FineTuningDisposition, FineTuningPolicy
from .replay_store import ReplayStore


REQUIRED_STAGE9_EXPORTS = {
    "ControlledTuningPlan",
    "DatasetRole",
    "FineTuningAnalyzer",
    "FineTuningCandidate",
    "FineTuningDataset",
    "FineTuningDatasetCompiler",
    "FineTuningDisposition",
    "FineTuningEligibilityResult",
    "FineTuningEligibilityScanner",
    "FineTuningEligibilityStatus",
    "FineTuningEvidenceStore",
    "FineTuningExample",
    "FineTuningLab",
    "FineTuningLabStatus",
    "FineTuningPlanStatus",
    "FineTuningPlanner",
    "FineTuningPolicy",
    "FineTuningQualification",
    "FineTuningStoreValidation",
    "plan_eligible_fine_tuning",
}

REQUIRED_STAGE9_FILES = (
    "src/inverted/capability_ratchet/fine_tuning_core.py",
    "src/inverted/capability_ratchet/fine_tuning_store.py",
    "src/inverted/capability_ratchet/fine_tuning_eligibility.py",
    "src/inverted/capability_ratchet/fine_tuning_dataset.py",
    "src/inverted/capability_ratchet/fine_tuning_planner.py",
    "src/inverted/capability_ratchet/fine_tuning_analysis.py",
    "src/inverted/capability_ratchet/fine_tuning_lab.py",
    "src/inverted/capability_ratchet/fine_tuning_cli.py",
    "tests/test_capability_ratchet_fine_tuning_core.py",
    "tests/test_capability_ratchet_fine_tuning_store.py",
    "tests/test_capability_ratchet_fine_tuning_eligibility.py",
    "tests/test_capability_ratchet_fine_tuning_dataset.py",
    "tests/test_capability_ratchet_fine_tuning_planner.py",
    "tests/test_capability_ratchet_fine_tuning_analysis.py",
    "tests/test_capability_ratchet_fine_tuning_lab.py",
    "tests/test_capability_ratchet_fine_tuning_cli.py",
    "tests/test_capability_ratchet_fine_tuning_audit_closure.py",
    "tests/test_capability_ratchet_fine_tuning_workflow_closure.py",
    ".github/workflows/v3-stage9-completion.yml",
)

EXPECTED_FINE_TUNING_COMMANDS = {
    "scan-fine-tuning-eligibility",
    "plan-fine-tuning",
    "show-fine-tuning-candidate",
    "show-fine-tuning-qualification",
    "export-fine-tuning-dataset",
}

_FORBIDDEN_NETWORK_ROOTS = frozenset({"httpx", "requests", "socket", "urllib"})
_FORBIDDEN_ADAPTER_NAMES = frozenset({"QwenOllamaAdapter", "QwenReplayAdapter"})


def _read(repo: Path, relative: str) -> str:
    return (repo / relative).read_text(encoding="utf-8")


def _parser_surface() -> tuple[set[str], dict[str, set[str]]]:
    parser = argparse.ArgumentParser(prog="inverted.capability_ratchet")
    sub = parser.add_subparsers(dest="command", required=True)
    add_fine_tuning_parsers(sub)
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        commands = set(action.choices)
        options = {
            name: {
                option
                for item in selected._actions
                for option in item.option_strings
            }
            for name, selected in action.choices.items()
        }
        return commands, options
    return set(), {}


def _forbidden_live_code_refs(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _FORBIDDEN_NETWORK_ROOTS:
                    hits.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in _FORBIDDEN_NETWORK_ROOTS:
                hits.add(module or root)
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_ADAPTER_NAMES:
            hits.add(node.id)
    return tuple(sorted(hits))


def _has_independent_fine_tuning_trainer(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            lowered = node.name.lower()
            if lowered.startswith("finetuning") and (
                lowered.endswith("executor") or lowered.endswith("trainer")
            ):
                return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
            "train",
            "execute_training",
            "run_training",
            "execute_fine_tuning",
        }:
            return True
    return False


def stage9_semantic_checks(
    repo: Path,
    replay_root: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Prove Stage 9 remains qualification-only, leakage-safe, and zero-call."""

    findings: list[str] = []
    policy = FineTuningPolicy()

    missing_exports = sorted(REQUIRED_STAGE9_EXPORTS - set(cr.__all__))
    if missing_exports:
        findings.append(f"Stage-9 public exports missing: {missing_exports}")

    missing_files = [path for path in REQUIRED_STAGE9_FILES if not (repo / path).is_file()]
    if missing_files:
        findings.append(f"Stage-9 source/tests/workflow missing: {missing_files}")

    stage9_tests = tuple((repo / "tests").glob("test_capability_ratchet_fine_tuning_*.py"))
    if len(stage9_tests) < 10:
        findings.append("Stage-9 fine-tuning test surface is missing or collapsed")

    core_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_core.py")
    store_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_store.py")
    eligibility_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_eligibility.py")
    dataset_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_dataset.py")
    planner_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_planner.py")
    analysis_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_analysis.py")
    lab_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_lab.py")
    cli_source = _read(repo, "src/inverted/capability_ratchet/fine_tuning_cli.py")
    all_sources = (
        core_source,
        store_source,
        eligibility_source,
        dataset_source,
        planner_source,
        analysis_source,
        lab_source,
        cli_source,
    )

    commands, options = _parser_surface()
    stage9_cli_surface_contract = (
        commands == EXPECTED_FINE_TUNING_COMMANDS
        and commands == set(FINE_TUNING_COMMANDS)
        and "execute-fine-tuning" not in commands
        and "train-fine-tuning" not in commands
        and all("--allow-model-calls" not in value for value in options.values())
        and {"--auto-eligible", "--candidate-id"}.issubset(
            options.get("plan-fine-tuning", set())
        )
        and "--candidate-id" in options.get("show-fine-tuning-candidate", set())
        and "--qualification-id" in options.get("show-fine-tuning-qualification", set())
        and {"--candidate-id", "--output"}.issubset(
            options.get("export-fine-tuning-dataset", set())
        )
    )
    if not stage9_cli_surface_contract:
        findings.append(
            f"Stage-9 safe CLI surface mismatch: commands={sorted(commands)} options={options}"
        )

    zero_call_sources = (core_source, eligibility_source, dataset_source, planner_source, cli_source)
    zero_call_refs = tuple(
        sorted({ref for source in zero_call_sources for ref in _forbidden_live_code_refs(source)})
    )
    stage9_zero_call_contract = (
        policy.development_model_call_budget == 0
        and "MODEL_CALLS" in cli_source
        and "model_calls != 0" in eligibility_source
        and "projected_development_model_calls != 0" in core_source
        and not zero_call_refs
        and all("ReplayExecutor(" not in source for source in zero_call_sources)
    )
    if not stage9_zero_call_contract:
        findings.append(
            "Stage-9 qualification/planning can no longer be proven zero-call"
            + (f": live refs={list(zero_call_refs)}" if zero_call_refs else "")
        )

    stage9_live_refs = tuple(
        sorted({ref for source in all_sources for ref in _forbidden_live_code_refs(source)})
    )
    independent_trainer = any(_has_independent_fine_tuning_trainer(source) for source in all_sources)
    stage9_no_independent_trainer_contract = (
        not independent_trainer
        and not stage9_live_refs
        and all("ReplayExecutor(" not in source for source in all_sources)
        and "FineTuningExecutor" not in set(cr.__all__)
        and "FineTuningTrainer" not in set(cr.__all__)
        and "intentionally exposes no training execution method" in lab_source
    )
    if not stage9_no_independent_trainer_contract:
        findings.append(
            "Stage-9 introduced an executor/trainer/live transport"
            f": independent_trainer={independent_trainer}, live_refs={list(stage9_live_refs)}"
        )

    stage9_model_internal_owner_contract = (
        policy.require_model_internal_residual is True
        and "CompilationKind.FINE_TUNE_CANDIDATE not in kinds" in eligibility_source
        and "model_internal_residual" in eligibility_source
        and "MODEL_INTERNAL residual ownership is required for fine-tuning qualification" in core_source
    )
    if not stage9_model_internal_owner_contract:
        findings.append("Stage-9 can admit a non-model-owned residual")

    stage9_cheaper_owner_veto_contract = (
        policy.require_cheaper_owners_resolved is True
        and "_CHEAPER_THAN_FINE_TUNE" in eligibility_source
        and "FineTuningEligibilityStatus.CHEAPER_OWNER_UNRESOLVED" in eligibility_source
        and "cheaper owners must be resolved before Stage-9 qualification" in core_source
    )
    if not stage9_cheaper_owner_veto_contract:
        findings.append("Stage-9 can bypass cheaper-owner exhaustion")

    stage9_recurrence_contract = (
        policy.minimum_independent_failures >= 2
        and "independent failure recurrence requires at least two failures" in core_source
        and "fine-tuning requires recurrent independent failure instances" in eligibility_source
    )
    if not stage9_recurrence_contract:
        findings.append("Stage-9 can qualify from a one-off failure")

    stage9_stage8_generalization_gate = (
        policy.require_generalization_evidence is True
        and "FineTuningEligibilityStatus.INSUFFICIENT_GENERALIZATION_EVIDENCE" in eligibility_source
        and "generalization evidence is required before Stage-9 qualification" in core_source
    )
    if not stage9_stage8_generalization_gate:
        findings.append("Stage-9 can bypass accepted Stage-8 generalization evidence")

    stage9_protected_partition_veto_contract = (
        policy.protect_fresh_and_sealed is True
        and "FRESH/SEALED protected partitions cannot enter Stage-9 qualification" in core_source
        and "FRESH/SEALED protected partitions cannot enter Stage-9 datasets" in core_source
        and "FRESH/SEALED evidence is protected from Stage-9 qualification" in eligibility_source
    )
    if not stage9_protected_partition_veto_contract:
        findings.append("Stage-9 FRESH/SEALED protection can be bypassed")

    stage9_train_eval_disjoint_contract = (
        policy.require_disjoint_train_eval is True
        and "train/eval failure lineage must be disjoint" in core_source
        and "train/eval source content hashes must be disjoint to prevent leakage" in core_source
        and "train/eval example IDs must be disjoint" in core_source
    )
    if not stage9_train_eval_disjoint_contract:
        findings.append("Stage-9 train/eval separation is incomplete")

    stage9_leakage_veto_contract = (
        policy.require_no_oracle_leakage is True
        and "_FORBIDDEN_FRAGMENTS" in core_source
        and "_FORBIDDEN" in store_source
        and "hidden reasoning/oracle target material is forbidden" in core_source
        and "duplicates forbidden raw/oracle material" in store_source
    )
    if not stage9_leakage_veto_contract:
        findings.append("Stage-9 hidden reasoning/oracle leakage veto is incomplete")

    stage9_observable_target_contract = (
        policy.require_observable_targets is True
        and "_ALLOWED_TARGET_TYPES" in core_source
        and "hidden reasoning/oracle target types are forbidden; target must be observable" in core_source
        and "observable_target_ref" in core_source
        and "observable_target_hash" in core_source
    )
    if not stage9_observable_target_contract:
        findings.append("Stage-9 can train against a hidden/non-observable target")

    stage9_regression_negative_transfer_contract = (
        policy.require_regression_suite is True
        and "regression evidence is required for Stage-9 dataset packaging" in dataset_source
        and "negative-transfer evidence is required for Stage-9 dataset packaging" in dataset_source
        and "regression_evidence_refs" in core_source
        and "negative_transfer_refs" in core_source
    )
    if not stage9_regression_negative_transfer_contract:
        findings.append("Stage-9 regression/negative-transfer evidence is incomplete")

    promotion_values = {item.value for item in PromotionState}
    disposition_values = {item.value for item in FineTuningDisposition}
    stage9_qualification_not_training_contract = (
        promotion_values.isdisjoint(disposition_values)
        and policy.certification_allowed is False
        and policy.deployment_allowed is False
        and policy.training_authorized_by_default is False
        and "Stage-9 qualification is not training, certification, or deployment" in core_source
        and "training_completed: bool = False" in core_source
        and "certified: bool = False" in core_source
        and "deployment_allowed: bool = False" in core_source
    )
    if not stage9_qualification_not_training_contract:
        findings.append("Stage-9 qualification can be mistaken for training/certification/deployment")

    stage9_not_authorized_contract = (
        policy.training_authorized_by_default is False
        and 'authorization_status: str = "NOT_AUTHORIZED"' in core_source
        and "training_authorized: bool = False" in core_source
        and "Stage-9 controlled lane must remain NOT_AUTHORIZED" in core_source
        and "projected_development_model_calls: int = 0" in core_source
    )
    if not stage9_not_authorized_contract:
        findings.append("Stage-9 can silently authorize a training lane")

    stage9_stage11_confirmation_contract = (
        "stage11_confirmation_required: bool = True" in core_source
        and core_source.count("Stage 11 confirmation remains mandatory") >= 2
        and "stage11_confirmation_required" in store_source
        and "stage11_confirmation_required" in cli_source
    )
    if not stage9_stage11_confirmation_contract:
        findings.append("Stage-9 can bypass mandatory Stage-11 confirmation")

    replay = ReplayStore(replay_root)
    records = replay.records() if replay.validate().ok else ()
    stage9_certified = [
        item
        for item in records
        if isinstance(item, PromotionEvent)
        and item.to_state is PromotionState.CERTIFIED
        and str(item.metadata.get("stage", "")).upper() in {"STAGE9", "STAGE_9", "9"}
    ]
    stage9_certified_event_count = len(stage9_certified)
    if stage9_certified_event_count:
        findings.append(
            f"Stage-9 CERTIFIED promotion events are forbidden: {stage9_certified_event_count}"
        )

    payload = {
        "stage9_cli_surface_contract": stage9_cli_surface_contract,
        "stage9_zero_call_contract": stage9_zero_call_contract,
        "stage9_no_independent_trainer_contract": stage9_no_independent_trainer_contract,
        "stage9_model_internal_owner_contract": stage9_model_internal_owner_contract,
        "stage9_cheaper_owner_veto_contract": stage9_cheaper_owner_veto_contract,
        "stage9_recurrence_contract": stage9_recurrence_contract,
        "stage9_stage8_generalization_gate": stage9_stage8_generalization_gate,
        "stage9_protected_partition_veto_contract": stage9_protected_partition_veto_contract,
        "stage9_train_eval_disjoint_contract": stage9_train_eval_disjoint_contract,
        "stage9_leakage_veto_contract": stage9_leakage_veto_contract,
        "stage9_observable_target_contract": stage9_observable_target_contract,
        "stage9_regression_negative_transfer_contract": stage9_regression_negative_transfer_contract,
        "stage9_qualification_not_training_contract": stage9_qualification_not_training_contract,
        "stage9_not_authorized_contract": stage9_not_authorized_contract,
        "stage9_stage11_confirmation_contract": stage9_stage11_confirmation_contract,
        "stage9_certified_event_count": stage9_certified_event_count,
    }
    return findings, payload
