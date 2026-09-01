from io import StringIO

from inverted.test3_s1_progress import InPlaceS1Progress


def test_s1_progress_line_shows_percent_elapsed_remaining_and_eta():
    stream = StringIO()
    progress = InPlaceS1Progress(stream=stream, width=16)

    progress.update(
        completed_tasks=25,
        total_tasks=100,
        physical_calls=50,
        call_budget=200,
        arm_id="S1-A1",
        task_id="task-25",
    )

    text = stream.getvalue().lower()
    assert "25.0%" in text
    assert "elapsed" in text
    assert "left" in text
    assert "eta" in text
    assert "50/200 calls" in text
