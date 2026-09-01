from pathlib import Path


def test_readme_freezes_universal_campaign_progress_rule():
    text = Path("README.md").read_text(encoding="utf-8").lower()

    assert "universal campaign progress rule" in text
    assert "every future campaign section" in text
    assert "enabled by default" in text
    assert "completed/total work units" in text
    assert "physical model calls used/total" in text
    assert "current arm/phase" in text
    assert "flush" in text
    assert "no estimated time" in text
    assert "must not alter" in text
    assert "scientific accounting" in text
