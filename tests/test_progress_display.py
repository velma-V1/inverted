from datetime import datetime, timedelta, timezone
from io import StringIO

from inverted.progress import InPlaceProgress, _format_progress_line


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


def test_narrow_progress_line_preserves_required_small_window_information():
    now = datetime(2026, 9, 3, 9, 0, 0, tzinfo=timezone(timedelta(hours=-4), name="EDT"))
    line = _format_progress_line(
        completed=140,
        total=200,
        initial_completed=0,
        elapsed_s=2520.0,
        now=now,
        current="D3.4/A2",
        terminal_width=58,
        calls_used=120,
        calls_available=300,
    )

    assert len(line) <= 58
    assert "70.0%" in line
    assert "140/200" in line
    assert "L60" in line
    assert "ETA" in line
    assert "C120/300" in line


def test_progress_line_clamps_negative_counters_and_handles_zero_total():
    now = datetime(2026, 9, 3, 9, 0, 0, tzinfo=timezone.utc)
    line = _format_progress_line(
        completed=-5,
        total=0,
        initial_completed=0,
        elapsed_s=1.0,
        now=now,
        current="preflight",
        terminal_width=50,
    )

    assert "-5" not in line
    assert "L-" not in line
    assert "%" in line


def test_in_place_progress_uses_same_stream_and_finishes_with_one_newline():
    stream = StringIO()
    progress = InPlaceProgress(stream=stream, interactive=True, min_interval_s=0.0, terminal_width=64)
    progress.update(completed=1, total=4, current="D3.1", calls_used=1, calls_available=10)
    progress.update(completed=4, total=4, current="done", calls_used=4, calls_available=10, force=True)
    progress.finish()

    output = stream.getvalue()
    assert "\r" in output
    assert output.endswith("\n")
    assert not output.endswith("\n\n")
    assert "100.0%" in output


def test_noninteractive_progress_falls_back_to_compact_periodic_lines():
    stream = StringIO()
    progress = InPlaceProgress(stream=stream, interactive=False, min_interval_s=0.0, terminal_width=54)
    progress.update(completed=1, total=2, current="D3.2", calls_used=1, calls_available=5)
    progress.finish()

    output = stream.getvalue()
    assert "\r" not in output
    assert output.endswith("\n")
    assert "50.0%" in output
