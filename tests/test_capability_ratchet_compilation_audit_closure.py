from __future__ import annotations

import runpy
from pathlib import Path

import inverted.capability_ratchet as cr
from inverted.capability_ratchet.compilation_core import (
    COMPILATION_KIND_ORDER,
    CompilationKind,
)


REQUIRED_PUBLIC = {
    "CompilationKind",
    "CompilationEligibilityStatus",
    "CompilationDisposition",
    "CompilationCandidate",
    "CompilationPlan",
    "CompiledCapability",
    "CompilationPolicy",
    "CompilationEvidenceStore",
    "CompilationEligibilityScanner",
    "CompilationPlanner",
    "CapabilityCompiler",
    "plan_eligible_compilation",
}

EXPECTED_OWNER_ORDER = (
    CompilationKind.DETERMINISTIC_RULE,
    CompilationKind.STATE_REPRESENTATION,
    CompilationKind.FORMATTER_PARSER_VALIDATOR,
    CompilationKind.TOOL_POLICY,
    CompilationKind.SKILL_POLICY,
    CompilationKind.REASONING_POLICY,
    CompilationKind.VERIFIER_RECOVERY_POLICY,
    CompilationKind.FINE_TUNE_CANDIDATE,
    CompilationKind.ESCALATION_POLICY,
    CompilationKind.SAFE_STOP_BOUNDARY,
)


def test_stage8_public_contract_and_owner_order_cannot_silently_change() -> None:
    assert REQUIRED_PUBLIC.issubset(set(cr.__all__))
    for name in REQUIRED_PUBLIC:
        assert hasattr(cr, name)
    assert COMPILATION_KIND_ORDER == EXPECTED_OWNER_ORDER
    assert not hasattr(cr, "CompilationExecutor")


def test_permanent_audit_covers_stage8_compilation_boundaries() -> None:
    text = Path("scripts/audit-v3-replay-foundation.py").read_text(encoding="utf-8")
    required_tokens = (
        "compilation_core.py",
        "compilation_store.py",
        "compilation_eligibility.py",
        "compilation_planner.py",
        "compilation_compiler.py",
        "compilation_cli.py",
        "test_capability_ratchet_compilation_cli.py",
        "EXPECTED_COMPILATION_KIND_ORDER",
        "stage8_cli_surface_contract",
        "stage8_zero_call_contract",
        "stage8_no_independent_executor_contract",
        "stage8_owner_order_contract",
        "stage8_instance_patch_veto_contract",
        "stage8_stage456_feedback_gate",
        "stage8_protected_partition_veto_contract",
        "stage8_cheapest_owner_contract",
        "stage8_observable_trigger_contract",
        "stage8_negative_transfer_contract",
        "stage8_version_rollback_contract",
        "stage8_deployment_veto_contract",
        "stage8_deterministic_catalog_contract",
        "stage8_source_reference_contract",
        "stage8_certified_event_count",
    )
    missing = [token for token in required_tokens if token not in text]
    assert not missing, missing


def test_stage8_semantic_audit_is_clean_on_repository_source(tmp_path: Path) -> None:
    audit = runpy.run_path(str(Path("scripts/audit-v3-replay-foundation.py")))
    findings, payload = audit["_stage8_semantic_checks"](Path.cwd(), tmp_path / "replay")
    assert findings == []
    boolean_contracts = {
        key: value
        for key, value in payload.items()
        if key.startswith("stage8_") and key != "stage8_certified_event_count"
    }
    assert boolean_contracts
    assert all(boolean_contracts.values()), boolean_contracts
    assert payload["stage8_certified_event_count"] == 0


def test_stage8_cli_and_compiler_have_no_execution_surface() -> None:
    cli = Path("src/inverted/capability_ratchet/compilation_cli.py").read_text(encoding="utf-8")
    compiler = Path("src/inverted/capability_ratchet/compilation_compiler.py").read_text(encoding="utf-8")
    for forbidden in (
        "execute-compilation",
        "--allow-model-calls",
        "CompilationExecutor",
        "ReplayExecutor(",
        "QwenReplayAdapter",
        "QwenOllamaAdapter",
    ):
        assert forbidden not in cli
        assert forbidden not in compiler
