from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/v3-stage9-completion.yml")
AUDIT = Path("scripts/audit-v3-replay-foundation.py")


def test_stage9_completion_workflow_cannot_silently_disappear() -> None:
    assert WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "name: v3-stage9-completion",
        "stage9-platform-matrix",
        'python: "3.11"',
        'python: "3.12"',
        'python: "3.14"',
        "windows-latest",
        "Run dedicated Stage-9 fine-tuning suite",
        "Run full capability-ratchet suite",
        "Run explicit V2 regression suite",
        "Run full repository regression on Linux",
        "Verify tracked evidence privacy",
        "Seed canonical historical replay corpus with zero inference",
        "Run permanent replay Stage-5/6/7/8/9 omission audit",
        "Scan historical Stage-9 eligibility with zero model calls",
        "Plan historical Stage-9 work with zero model calls",
        "Summarize deterministic Stage-9 dataset state",
        "Enforce Stage-9 completion invariants",
        "Verify tracked tree remains clean",
        "v3-stage9-completion-evidence",
        "STAGE9-COMPLETION.json",
        "STAGE9_COMPLETION",
        "MODEL_CALLS",
        "historical_stage9_status",
        "eligible_candidates",
        "qualified_lanes",
        "dataset_count",
        "dataset_hashes",
        "stage9_cheaper_owner_veto_contract",
        "stage9_recurrence_contract",
        "stage9_leakage_veto_contract",
        "stage9_train_eval_disjoint_contract",
        "stage9_not_authorized_contract",
        "stage9_stage11_confirmation_contract",
        "stage9_certified_event_count",
        "forgotten_count",
        "orphan_asset_count",
        "privacy_matches",
    )
    missing = [token for token in required if token not in text]
    assert not missing, missing


def test_stage9_completion_workflow_has_no_execution_or_live_inference_lane() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "execute-fine-tuning",
        "train-fine-tuning",
        "--allow-model-calls",
        "ollama",
        "QwenOllamaAdapter",
        "QwenReplayAdapter",
    ):
        assert forbidden not in text


def test_permanent_audit_requires_stage9_completion_workflow() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    assert '".github/workflows/v3-stage9-completion.yml"' in text
