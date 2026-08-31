from pathlib import Path
import ast


VP = Path("tools/vp")


def _vp_text() -> str:
    return VP.read_text(encoding="utf-8")


def _source_gate_python(text: str) -> str:
    marker = '"$PY" - "$OUT/source-dirty-paths.txt" > "$OUT/source-dirty-relevance.txt" <<\'PY\''
    start = text.index(marker) + len(marker)
    end = text.index("\nPY\n", start)
    return text[start:end].lstrip("\n")


def test_vp_bash_syntax_is_valid():
    import subprocess

    result = subprocess.run(["bash", "-n", str(VP)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_vp_embedded_source_gate_python_is_valid():
    ast.parse(_source_gate_python(_vp_text()))


def test_vp_preserves_windows_git_line_boundaries():
    text = _vp_text()
    source_gate = text[text.index("# WINDOWS-SOURCE WORKTREE AUTHORITY"):text.index("# HOST / WSL SNAPSHOT")]
    assert "tr -d '\\n'" not in source_gate
    assert source_gate.count("tr -d '\\r'") >= 2


def test_vp_has_no_obsolete_tracked_010_watcher_allowance():
    text = _vp_text()
    assert '"scripts/wait-for-010-and-run-inverted.ps1",' not in text
