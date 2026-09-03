from pathlib import Path


SCRIPT = Path("scripts/run-harvest-d-d3.ps1")


def test_d3_launcher_expands_test_glob_in_powershell_before_pytest() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    # pytest does not expand shell globs itself on Windows. The PowerShell
    # launcher must enumerate the files and splat the resulting array.
    assert 'Get-ChildItem -Path "tests" -Filter "test_harvest_d_d3_*.py"' in text
    assert 'python -m pytest -q @ValidationTests' in text
    assert 'python -m pytest -q tests/test_harvest_d_d3_*.py' not in text


def test_d3_launcher_fails_closed_if_no_focused_tests_are_found() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '$D3Tests.Count -eq 0' in text
    assert 'no d3 focused tests were found; no model calls were started' in text.lower()
