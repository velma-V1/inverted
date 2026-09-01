from io import StringIO
from os import terminal_size
from types import SimpleNamespace

import inverted.test3_s2_progress as progress_module
from inverted.test3_s2_progress import InPlaceS2Progress, S2ProgressTracker


def test_s2_progress_auto_fits_72_column_split_screen_with_required_fields(monkeypatch):
    monkeypatch.setattr(
        progress_module,
        "shutil",
        SimpleNamespace(get_terminal_size=lambda fallback=(80, 24): terminal_size((72, 24))),
    )
    stream = StringIO()
    progress = InPlaceS2Progress(stream=stream, width=16)
    progress.update(
        completed_trials=90,
        total_trials=360,
        physical_calls=180,
        call_budget=720,
        arm_id="S2-B3",
        phase="adaptive",
    )
    line = stream.getvalue().split("\r")[-1].rstrip()
    lower = line.lower()
    assert len(line) <= 71
    assert "[" in line and "]" in line
    assert "%" in line
    assert "90/360" in line
    assert "180/720" in line
    assert "b3" in lower
    assert "elapsed" in lower
    assert "left" in lower
    assert "eta" in lower


def test_s2_tracker_finishes_exactly_one_newline_and_counts_calls():
    stream = StringIO()
    progress = InPlaceS2Progress(stream=stream)
    tracker = S2ProgressTracker(progress, total_trials=360, call_budget=720)
    tracker.call_started("case-a-S2-B0", phase="fixed")
    tracker.call_started("case-a-S2-B0", phase="fixed")
    tracker.call_started("case-a-S2-B1", phase="family")
    tracker.finish(mark_current_complete=True)
    assert tracker.physical_calls == 3
    assert stream.getvalue().endswith("\n")
    assert not stream.getvalue().endswith("\n\n")
