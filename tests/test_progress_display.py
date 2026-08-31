from datetime import datetime, timedelta, timezone

from inverted.cli import _format_progress_line


def test_collective_progress_line_reports_completion_time_left_and_eta():
    now = datetime(2026, 8, 31, 8, 0, 0, tzinfo=timezone(timedelta(hours=-4), name="EDT"))

    line = _format_progress_line(
        completed=3240,
        total=6480,
        initial_completed=0,
        elapsed_s=3600.0,
        now=now,
        current="model=qwen3.5:9b-q8_0 arm=D_INVERTED family=state complexity=2",
    )

    assert line.startswith("PROGRESS [")
    assert "3240/6480" in line
    assert "50.00%" in line
    assert "left=01:00:00" in line
    assert "ETA=2026-08-31 09:00:00 EDT" in line
    assert "model=qwen3.5:9b-q8_0" in line


def test_collective_progress_line_uses_resume_delta_for_eta():
    now = datetime(2026, 8, 31, 8, 0, 0, tzinfo=timezone(timedelta(hours=-4), name="EDT"))

    line = _format_progress_line(
        completed=2447,
        total=6480,
        initial_completed=2446,
        elapsed_s=10.0,
        now=now,
        current="model=llama3.1:8b arm=A_DIRECT family=policy complexity=1",
    )

    assert "2447/6480" in line
    assert "left=11:12:10" in line
    assert "ETA=2026-08-31 19:12:10 EDT" in line


def test_collective_progress_line_marks_eta_warming_up_before_new_completion():
    now = datetime(2026, 8, 31, 8, 0, 0, tzinfo=timezone.utc)

    line = _format_progress_line(
        completed=2446,
        total=6480,
        initial_completed=2446,
        elapsed_s=0.0,
        now=now,
        current="resume",
    )

    assert "2446/6480" in line
    assert "left=warming-up" in line
    assert "ETA=warming-up" in line
