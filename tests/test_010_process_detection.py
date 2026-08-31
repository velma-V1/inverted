from pathlib import Path


def test_watcher_supports_exact_010_pid_and_module_pattern():
    text = Path("scripts/wait-for-010-and-run-inverted.ps1").read_text(encoding="utf-8")
    assert '[int]$Expected010ProcessId = 0' in text
    assert 'alien_lab\\.computational_atlas_live_experiment' in text
    assert 'ProcessId = $Expected010ProcessId' in text
    assert '$script:Locked010ProcessId' in text


def test_wrapper_passes_exact_010_pid_to_watcher():
    text = Path("scripts/run-overnight-handoff.ps1").read_text(encoding="utf-8")
    assert '[int]$Expected010ProcessId = 0' in text
    assert '-Expected010ProcessId $Expected010ProcessId' in text
