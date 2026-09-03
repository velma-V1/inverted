from __future__ import annotations

from datetime import datetime, timedelta
import shutil
import sys
import time
from typing import TextIO


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_compact_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def _progress_values(
    *,
    completed: int,
    total: int,
    initial_completed: int,
    elapsed_s: float,
    now: datetime,
) -> tuple[int, int, int, float, str, str, str, str]:
    safe_total = max(0, int(total))
    safe_completed = min(max(0, int(completed)), safe_total) if safe_total else max(0, int(completed))
    remaining = max(0, safe_total - safe_completed)
    pct = 100.0 * safe_completed / safe_total if safe_total else 100.0

    measured_completed = max(0, safe_completed - max(0, int(initial_completed)))
    if measured_completed <= 0 or elapsed_s <= 0.0 or (safe_total and safe_completed >= safe_total):
        if safe_total == 0 or safe_completed >= safe_total:
            left_text = "00:00:00"
            compact_left = "0s"
            eta = now
            eta_text = eta.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()
            compact_eta = eta.strftime("%H:%M")
        else:
            left_text = "warming-up"
            compact_left = "--"
            eta_text = "warming-up"
            compact_eta = "--:--"
    else:
        units_per_second = measured_completed / elapsed_s
        seconds_left = remaining / units_per_second
        eta = now + timedelta(seconds=seconds_left)
        left_text = _format_duration(seconds_left)
        compact_left = _format_compact_duration(seconds_left)
        eta_text = eta.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()
        compact_eta = eta.strftime("%H:%M")

    return (
        safe_completed,
        safe_total,
        remaining,
        pct,
        left_text,
        eta_text,
        compact_left,
        compact_eta,
    )


def _format_progress_line(
    *,
    completed: int,
    total: int,
    initial_completed: int,
    elapsed_s: float,
    now: datetime,
    current: str,
    width: int = 30,
    terminal_width: int | None = None,
    calls_used: int | None = None,
    calls_available: int | None = None,
) -> str:
    (
        safe_completed,
        safe_total,
        remaining,
        pct,
        left_text,
        eta_text,
        compact_left,
        compact_eta,
    ) = _progress_values(
        completed=completed,
        total=total,
        initial_completed=initial_completed,
        elapsed_s=elapsed_s,
        now=now,
    )

    if terminal_width is not None and int(terminal_width) < 88:
        max_chars = max(32, int(terminal_width))
        call_text = ""
        if calls_used is not None or calls_available is not None:
            safe_calls_used = max(0, int(calls_used or 0))
            safe_calls_available = max(0, int(calls_available or 0))
            call_text = f" C{safe_calls_used}/{safe_calls_available}"

        fixed = (
            f" {pct:.1f}% {safe_completed}/{safe_total} L{remaining}"
            f"{call_text} {compact_left} ETA{compact_eta}"
        )
        bar_width = max(3, min(10, max_chars - len(fixed) - 2))
        ratio = (safe_completed / safe_total) if safe_total else 1.0
        filled = min(bar_width, max(0, int(round(bar_width * ratio))))
        line = f"[{'#' * filled}{'-' * (bar_width - filled)}]{fixed}"

        # Current phase/task is useful but lower priority than the mandatory
        # compact counters. Include it only when it fits without truncating them.
        current_text = str(current or "").strip()
        if current_text:
            room = max_chars - len(line) - 1
            if room >= 4:
                line += " " + current_text[:room]
        return line[:max_chars]

    safe_width = max(1, int(width))
    filled = safe_width if not safe_total else min(
        safe_width,
        int(round(safe_width * safe_completed / safe_total)),
    )
    bar = f"[{'#' * filled}{'-' * (safe_width - filled)}]"
    suffix = f" {current}" if current else ""
    call_suffix = ""
    if calls_used is not None or calls_available is not None:
        call_suffix = f" calls={max(0, int(calls_used or 0))}/{max(0, int(calls_available or 0))}"
    return (
        f"PROGRESS {bar} {safe_completed}/{safe_total} {pct:6.2f}% "
        f"remaining={remaining}{call_suffix} left={left_text} ETA={eta_text}{suffix}"
    )


class ProgressTracker:
    """Measures throughput only for work completed during the current process."""

    def __init__(self, initial_completed: int = 0) -> None:
        self.initial_completed = max(0, int(initial_completed))
        self.started_monotonic = time.monotonic()

    def render(
        self,
        completed: int,
        total: int,
        current: str,
        *,
        terminal_width: int | None = None,
        calls_used: int | None = None,
        calls_available: int | None = None,
    ) -> str:
        elapsed_s = max(0.0, time.monotonic() - self.started_monotonic)
        return _format_progress_line(
            completed=completed,
            total=total,
            initial_completed=self.initial_completed,
            elapsed_s=elapsed_s,
            now=datetime.now().astimezone(),
            current=current,
            terminal_width=terminal_width,
            calls_used=calls_used,
            calls_available=calls_available,
        )


class InPlaceProgress:
    """Compact same-terminal progress with a safe line-oriented fallback.

    This class is observability only: callers supply counters and it never
    changes scheduling, prompts, retries, budgets, or scientific decisions.
    """

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        interactive: bool | None = None,
        min_interval_s: float = 0.5,
        terminal_width: int | None = None,
        initial_completed: int = 0,
    ) -> None:
        self.stream = stream if stream is not None else sys.stdout
        if interactive is None:
            try:
                interactive = bool(self.stream.isatty())
            except (AttributeError, OSError):
                interactive = False
        self.interactive = bool(interactive)
        self.min_interval_s = max(0.0, float(min_interval_s))
        self.terminal_width = terminal_width
        self.initial_completed = max(0, int(initial_completed))
        self.started_monotonic = time.monotonic()
        self._last_emit_monotonic: float | None = None
        self._last_width = 0
        self._finished = False
        self._emitted = False

    def _width(self) -> int:
        if self.terminal_width is not None:
            return max(32, int(self.terminal_width))
        return max(32, int(shutil.get_terminal_size(fallback=(80, 24)).columns) - 1)

    def update(
        self,
        *,
        completed: int,
        total: int,
        current: str = "",
        calls_used: int | None = None,
        calls_available: int | None = None,
        force: bool = False,
    ) -> bool:
        if self._finished:
            return False
        now_mono = time.monotonic()
        if (
            not force
            and self._last_emit_monotonic is not None
            and now_mono - self._last_emit_monotonic < self.min_interval_s
        ):
            return False

        line = _format_progress_line(
            completed=completed,
            total=total,
            initial_completed=self.initial_completed,
            elapsed_s=max(0.0, now_mono - self.started_monotonic),
            now=datetime.now().astimezone(),
            current=current,
            terminal_width=self._width(),
            calls_used=calls_used,
            calls_available=calls_available,
        )

        if self.interactive:
            pad_width = max(self._last_width, len(line))
            self.stream.write("\r" + line.ljust(pad_width))
            self._last_width = len(line)
        else:
            self.stream.write(line + "\n")
        self.stream.flush()
        self._last_emit_monotonic = now_mono
        self._emitted = True
        return True

    def finish(self) -> None:
        if self._finished:
            return
        if self.interactive and self._emitted:
            self.stream.write("\n")
            self.stream.flush()
        self._finished = True
