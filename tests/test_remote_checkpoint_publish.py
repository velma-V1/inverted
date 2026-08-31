from pathlib import Path


def test_handoff_starts_nonblocking_checkpoint_publisher():
    text = Path("scripts/wait-for-010-and-run-inverted.ps1").read_text(encoding="utf-8")
    assert "publish-inverted-checkpoints.ps1" in text
    assert "Start-Job" in text
    assert "INVERTED_CHECKPOINT_PUBLISHER" in text


def test_checkpoint_publisher_uses_dedicated_results_branch_and_incremental_chunks():
    text = Path("scripts/publish-inverted-checkpoints.ps1").read_text(encoding="utf-8")
    assert 'results/$RunId' in text
    assert "checkpoint-" in text
    assert "progress.json" in text
    assert "Get-FileHash" in text
    assert "git" in text and "push" in text
    assert "StopSignal" in text


def test_checkpoint_publisher_never_deletes_local_checkpoint():
    text = Path("scripts/publish-inverted-checkpoints.ps1").read_text(encoding="utf-8")
    assert "Remove-Item $Checkpoint" not in text
