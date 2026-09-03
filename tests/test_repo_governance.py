from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "REPO_LAWS_AND_REGULATIONS.md"
ENTRYPOINTS = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    "MODEL_OPERATING_RULES.md",
)


def test_canonical_repo_laws_exist_and_preserve_core_principles() -> None:
    text = (ROOT / CANONICAL).read_text(encoding="utf-8")

    assert "My suggestion is a floor, not a ceiling" in text
    assert "Data collection is cheap; retesting is not" in text
    assert "project" in text.lower()
    assert "smallest" in text.lower()
    assert "ship" in text.lower()


def test_all_model_entrypoints_reference_canonical_repo_laws() -> None:
    for relative_path in ENTRYPOINTS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert CANONICAL in text, relative_path
