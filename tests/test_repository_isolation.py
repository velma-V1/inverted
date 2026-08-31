from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CROSS_REPO_FILES = (
    Path("scripts/wait-for-010-and-run-inverted.ps1"),
    Path("scripts/run-overnight-handoff.ps1"),
)

# Construct these so this guard does not flag its own source text.
CROSS_REPO_MARKERS = (
    "velma-" + "alien-stack-lab",
    "experiment/010-" + "computational-basis-atlas",
    "wait-for-010-" + "and-run-inverted.ps1",
)

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".ps1",
    ".toml",
    ".yaml",
    ".yml",
    ".txt",
    "",
}


def _tracked_text_candidates():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in {".git", "__pycache__", ".pytest_cache", ".hypothesis", ".ruff_cache", "build"} for part in rel.parts):
            continue
        if rel == Path("tests/test_repository_isolation.py"):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield rel, path


def test_cross_repo_handoff_files_are_absent():
    present = [str(path) for path in CROSS_REPO_FILES if (ROOT / path).exists()]
    assert not present, f"obsolete cross-repo handoff files remain: {present}"


def test_repository_has_no_alien_lab_cross_repo_pointers():
    offenders = []
    for rel, path in _tracked_text_candidates():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in CROSS_REPO_MARKERS:
            if marker in text:
                offenders.append(f"{rel}: {marker}")
    assert not offenders, "cross-repo pointers remain:\n" + "\n".join(offenders)
