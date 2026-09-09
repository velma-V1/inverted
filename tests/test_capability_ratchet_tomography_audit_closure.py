from __future__ import annotations

from pathlib import Path

import inverted.capability_ratchet as cr


REQUIRED_PUBLIC = {
    "TomographyAxis",
    "TomographyDisposition",
    "TomographyPolicy",
    "TomographyProbeSpec",
    "TomographyStudy",
    "TomographyOutcome",
    "TomographyAssessment",
    "TomographyEvidenceStore",
    "TomographyPlanner",
    "TomographyReplayCompiler",
    "TomographyAnalyzer",
    "TomographyLab",
    "classify_tomography_eligibility",
    "plan_eligible_tomography",
}


def test_stage7_public_contract_cannot_silently_disappear() -> None:
    assert REQUIRED_PUBLIC.issubset(set(cr.__all__))
    for name in REQUIRED_PUBLIC:
        assert hasattr(cr, name)


def test_permanent_audit_covers_stage7_tomography_boundaries() -> None:
    text = Path("scripts/audit-v3-replay-foundation.py").read_text(encoding="utf-8")
    required_tokens = (
        "tomography_core.py",
        "tomography_store.py",
        "tomography_eligibility.py",
        "tomography_planner.py",
        "tomography_replay.py",
        "tomography_analysis.py",
        "tomography_lab.py",
        "tomography_cli.py",
        "test_capability_ratchet_tomography_cli.py",
        "v3-stage7-completion.yml",
        "EXPECTED_TOMOGRAPHY_AXES",
        "stage7_cli_surface_contract",
        "stage7_zero_call_plan_contract",
        "stage7_no_independent_executor_contract",
        "stage7_canonical_replay_contract",
        "stage7_generic_third_retry_forbidden",
        "stage7_targeted_recovery_state_contract",
        "stage7_tool_axis_contract",
        "stage7_verifier_recovery_separation",
        "stage7_protected_partition_veto_contract",
        "stage7_certified_event_count",
        "stage7_disposition_promotion_separation",
        "stage7_stage456_feedback_gate",
    )
    missing = [token for token in required_tokens if token not in text]
    assert not missing, missing


def test_stage7_completion_workflow_is_zero_call_and_evidence_bearing() -> None:
    text = Path(".github/workflows/v3-stage7-completion.yml").read_text(encoding="utf-8")
    for token in (
        "tests/test_capability_ratchet_tomography_*.py",
        "tests/test_capability_ratchet_*.py",
        "audit-v3-replay-foundation.py",
        "scan-tomography-eligibility",
        "plan-tomography",
        "--auto-eligible",
        "MODEL_CALLS",
        "STAGE7_COMPLETION",
        "stage7_tool_axis_contract",
        "stage7_verifier_recovery_separation",
        "stage7_generic_third_retry_forbidden",
        "stage7_stage456_feedback_gate",
        "forgotten_count",
        "orphan_assets",
        "privacy_matches",
        "v3-stage7-completion-evidence",
    ):
        assert token in text
    assert "execute-tomography" not in text
    assert "--allow-model-calls" not in text
