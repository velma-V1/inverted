from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/v3-stage8-completion.yml")
AUDIT = Path("scripts/audit-v3-replay-foundation.py")


def test_stage8_completion_workflow_cannot_silently_disappear() -> None:
    assert WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "name: v3-stage8-completion",
        "stage8-platform-matrix",
        'python: "3.11"',
        'python: "3.12"',
        'python: "3.14"',
        "windows-latest",
        "Run dedicated Stage-8 compilation suite",
        "Run full capability-ratchet suite",
        "Run explicit V2 regression suite",
        "Run full repository regression on Linux",
        "Verify tracked evidence privacy",
        "Seed canonical historical replay corpus with zero inference",
        "Run permanent replay Stage-5/6/7/8 omission audit",
        "Scan historical Stage-8 eligibility with zero model calls",
        "Plan historical Stage-8 work with zero model calls",
        "Export deterministic Stage-8 capability catalog",
        "Enforce Stage-8 completion invariants",
        "Verify tracked tree remains clean",
        "v3-stage8-completion-evidence",
        "STAGE8-COMPLETION.json",
        "MODEL_CALLS",
        "forgotten_count",
        "orphan_asset_count",
        "privacy_matches",
        "catalog_hash",
        "stage8_certified_event_count",
    )
    missing = [token for token in required if token not in text]
    assert not missing, missing


def test_stage8_completion_workflow_has_no_execution_or_live_inference_lane() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "execute-compilation",
        "--allow-model-calls",
        "ollama",
        "QwenOllamaAdapter",
        "QwenReplayAdapter",
    ):
        assert forbidden not in text


def test_permanent_audit_requires_stage8_completion_workflow() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    assert '".github/workflows/v3-stage8-completion.yml"' in text
