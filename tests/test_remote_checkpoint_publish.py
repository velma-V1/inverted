from pathlib import Path


def test_handoff_supervisor_starts_nonblocking_checkpoint_publisher():
    text = Path("scripts/run-overnight-handoff.ps1").read_text(encoding="utf-8")
    assert "publish-inverted-checkpoints.ps1" in text
    assert "wait-for-010-and-run-inverted.ps1" in text
    assert "Start-Job" in text
    assert "INVERTED_CHECKPOINT_PUBLISHER" in text
    assert "publisher-wrapper-stop.signal" in text


def test_checkpoint_publisher_uses_separate_local_and_remote_results_branches_and_incremental_chunks():
    text = Path("scripts/publish-inverted-checkpoints.ps1").read_text(encoding="utf-8")
    assert '$Branch = "results/$RunId"' in text
    assert '$LocalBranch = "checkpoint-$RunId"' in text
    assert '$Branch = "results-$RunId"' not in text
    assert "progress.json" in text
    assert "Get-FileHash" in text
    assert "git" in text and "push" in text
    assert "StopSignal" in text


def test_checkpoint_publisher_never_deletes_local_checkpoint():
    text = Path("scripts/publish-inverted-checkpoints.ps1").read_text(encoding="utf-8")
    assert "Remove-Item $Checkpoint" not in text


def test_remote_publisher_failure_is_nonblocking_by_contract():
    text = Path("scripts/publish-inverted-checkpoints.ps1").read_text(encoding="utf-8")
    assert "CHECKPOINT PUBLISH FAILED" in text
    assert "Local checkpoint remains untouched" in text or "local checkpoint" in text.lower()
