from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preserve-harvest-d-d4-r1-evidence.ps1"


def test_publisher_script_exists_and_uses_validated_bundle_module():
    assert SCRIPT.is_file(), "D4/R1 evidence publisher script is missing"
    text = SCRIPT.read_text(encoding="utf-8")
    assert "inverted.harvest_d.d4_r1_evidence_bundle" in text
    assert "--d4-root" in text
    assert "--r1-root" in text
    assert "--implementation-commit" in text
    assert "--expected-qwen-model" in text


def test_publisher_uses_isolated_orphan_worktree_and_never_switches_active_checkout():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "git worktree add --detach" in text
    assert "git -C $Worktree switch --orphan $EvidenceBranch" in text
    assert "git -C $Worktree push origin" in text
    assert "live-evidence" in text
    assert "git switch --orphan $EvidenceBranch" not in text.replace("git -C $Worktree switch --orphan $EvidenceBranch", "")
    assert "git checkout" not in text


def test_publisher_fails_closed_if_evidence_branch_already_exists():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "git ls-remote" in text
    assert "git show-ref --verify" in text
    assert "already exists" in text


def test_publisher_is_zero_inference_and_cannot_rerun_d4_or_r1():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "run-harvest-d-d4-qwen-policy.ps1",
        "run-harvest-d-d3-closure-r1.ps1",
        "d4_qwen_cli",
        "d3_closure_r1_cli",
        "ollama run",
        "ollama serve",
    )
    for item in forbidden:
        assert item not in text
    assert "PackageOnly" in text


def test_publisher_records_current_implementation_commit_and_preserves_local_bundle():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "git rev-parse HEAD" in text
    assert "evidence_provenance.json" in text
    assert "SHA256SUMS-D4-R1-ARCHIVES.csv" in text
    assert "Remove-Item -Recurse -Force $BundleRoot" not in text
