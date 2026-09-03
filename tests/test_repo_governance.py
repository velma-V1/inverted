from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "REPO_LAWS_AND_REGULATIONS.md"
DIRECT_MODEL_ENTRYPOINTS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
)


def test_canonical_repo_laws_exist_and_preserve_core_principles() -> None:
    text = (ROOT / CANONICAL).read_text(encoding="utf-8")

    assert "My suggestion is a floor, not a ceiling" in text
    assert "Data collection is cheap; retesting is not" in text
    assert "PROJECT LOYALTY LAW" in text
    assert "COMPLEMENTARY PROJECT-PARTNER LAW" in text
    assert "AUTOMATIC PROJECT-DEPARTMENT ROUTING LAW" in text
    assert "RESEARCH SPECIALIST LAW" in text
    assert "HIGHEST SHIPPING TIER LAW" in text
    assert "smallest system" in text.lower()


def test_direct_model_entrypoints_reference_canonical_repo_laws() -> None:
    for relative_path in DIRECT_MODEL_ENTRYPOINTS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert CANONICAL in text, relative_path


def test_legacy_rules_file_redirects_to_canonical_repo_laws() -> None:
    text = (ROOT / "MODEL_OPERATING_RULES.md").read_text(encoding="utf-8")
    assert CANONICAL in text
    assert "superseded" in text.lower()


def test_readme_surfaces_the_governance_entrypoint() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "MODEL_OPERATING_RULES.md" in text or CANONICAL in text
