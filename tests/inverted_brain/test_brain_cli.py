from pathlib import Path

from inverted_brain.cli import main


def write_config(path: Path):
    path.write_text(
        "frontier_pool: 18\nharvest_cases: 4\nfresh_holdout: 24\nrun_ceiling: 120\n",
        encoding="utf-8",
    )


def test_cli_refuses_live_without_explicit_flag(tmp_path, capsys):
    cfg = tmp_path / "c.yaml"; write_config(cfg)
    rc = main(["--config", str(cfg), "--output-dir", str(tmp_path / "out")])
    assert rc == 4
    assert "REFUSING LIVE CAMPAIGN" in capsys.readouterr().out


def test_instrument_smoke_is_labeled_and_passes(tmp_path, capsys):
    cfg = tmp_path / "c.yaml"; write_config(cfg)
    rc = main(["--config", str(cfg), "--output-dir", str(tmp_path / "out"), "--instrument-smoke"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "INSTRUMENT VALIDATION" in out
    assert "NOT BRAIN EVIDENCE" in out
