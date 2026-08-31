from __future__ import annotations

from datetime import datetime, timedelta
import time


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_progress_line(
    *,
    completed: int,
    total: int,
    initial_completed: int,
    elapsed_s: float,
    now: datetime,
    current: str,
    width: int = 30,
) -> str:
    safe_total = max(0, int(total))
    safe_completed = min(max(0, int(completed)), safe_total) if safe_total else max(0, int(completed))
    pct = 100.0 * safe_completed / safe_total if safe_total else 100.0
    filled = width if not safe_total else min(width, int(round(width * safe_completed / safe_total)))
    bar = f"[{'#' * filled}{'-' * (width - filled)}]"

    measured_completed = max(0, safe_completed - max(0, int(initial_completed)))
    if measured_completed <= 0 or elapsed_s <= 0.0 or safe_completed >= safe_total:
        if safe_completed >= safe_total:
            left_text = "00:00:00"
            eta_text = now.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()
        else:
            left_text = "warming-up"
            eta_text = "warming-up"
    else:
        units_per_second = measured_completed / elapsed_s
        remaining = max(0, safe_total - safe_completed)
        seconds_left = remaining / units_per_second
        eta = now + timedelta(seconds=seconds_left)
        left_text = _format_duration(seconds_left)
        eta_text = eta.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()

    suffix = f" {current}" if current else ""
    return (
        f"PROGRESS {bar} {safe_completed}/{safe_total} {pct:6.2f}% "
        f"left={left_text} ETA={eta_text}{suffix}"
    )


class ProgressTracker:
    """Measures throughput only for work completed during the current process."""

    def __init__(self, initial_completed: int = 0) -> None:
        self.initial_completed = max(0, int(initial_completed))
        self.started_monotonic = time.monotonic()

    def render(self, completed: int, total: int, current: str) -> str:
        elapsed_s = max(0.0, time.monotonic() - self.started_monotonic)
        return _format_progress_line(
            completed=completed,
            total=total,
            initial_completed=self.initial_completed,
            elapsed_s=elapsed_s,
            now=datetime.now().astimezone(),
            current=current,
        )
