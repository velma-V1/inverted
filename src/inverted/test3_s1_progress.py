from __future__ import annotations

from datetime import datetime, timedelta
import sys
import time
from typing import Any, TextIO


def _format_duration(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class InPlaceS1Progress:
    """Render a bounded single-line S1 progress meter with display-only ETA telemetry."""

    def __init__(self, *, stream: TextIO | None = None, width: int = 16):
        self.stream = stream if stream is not None else sys.stdout
        self.width = min(20, max(10, int(width)))
        self._last_width = 0
        self._finished = False
        self._started_monotonic = time.monotonic()

    def update(
        self,
        *,
        completed_tasks: int,
        total_tasks: int,
        physical_calls: int,
        call_budget: int,
        arm_id: str = "",
        task_id: str = "",
    ) -> None:
        del task_id  # Full task IDs can wrap Windows terminals and create fake new bars.
        if self._finished:
            return

        total = max(1, int(total_tasks))
        completed = min(total, max(0, int(completed_tasks)))
        calls_total = max(0, int(call_budget))
        calls_done = max(0, int(physical_calls))

        task_ratio = completed / total
        if calls_total > 0:
            ratio = min(1.0, calls_done / calls_total)
        else:
            ratio = task_ratio

        filled = min(self.width, int(self.width * ratio))
        bar = "#" * filled + "-" * (self.width - filled)
        percent = ratio * 100.0

        elapsed = max(0.0, time.monotonic() - self._started_monotonic)
        if ratio > 0.0:
            remaining = max(0.0, elapsed * (1.0 - ratio) / ratio)
            eta = datetime.now().astimezone() + timedelta(seconds=remaining)
            left_text = _format_duration(remaining)
            eta_text = eta.strftime("%H:%M:%S")
        else:
            left_text = "--:--:--"
            eta_text = "--:--:--"

        arm = str(arm_id).strip()
        line = (
            f"S1 [{bar}] {percent:5.1f}% {completed}/{total} | "
            f"{calls_done}/{calls_total} calls | "
            f"elapsed {_format_duration(elapsed)} | left {left_text} | ETA {eta_text}"
        )
        if arm:
            line += f" | {arm[:8]}"

        # Keep the richer status bounded to a normal PowerShell terminal line.
        line = line[:112]
        padded = line.ljust(max(self._last_width, len(line)))
        self.stream.write("\r" + padded)
        self.stream.flush()
        self._last_width = len(line)

    def finish(self) -> None:
        if self._finished:
            return
        self.stream.write("\n")
        self.stream.flush()
        self._finished = True


class S1ProgressTracker:
    """Translate sequential physical calls into arm-task completion progress."""

    def __init__(self, progress: InPlaceS1Progress, *, total_tasks: int, call_budget: int):
        self.progress = progress
        self.total_tasks = max(0, int(total_tasks))
        self.call_budget = max(0, int(call_budget))
        self.current_trial_id: str | None = None
        self.completed_tasks = 0
        self.physical_calls = 0
        self.arm_id = ""
        self.task_id = ""

    @staticmethod
    def _trial_labels(trial_id: str) -> tuple[str, str]:
        marker = "-S1-A"
        index = trial_id.rfind(marker)
        if index < 0:
            return "", trial_id
        return trial_id[index + 1 :], trial_id[:index]

    def call_started(self, trial_id: str) -> None:
        trial = str(trial_id or "unknown")
        if self.current_trial_id is not None and trial != self.current_trial_id:
            self.completed_tasks = min(self.total_tasks, self.completed_tasks + 1)
        self.current_trial_id = trial
        self.arm_id, self.task_id = self._trial_labels(trial)
        self.physical_calls += 1
        self.progress.update(
            completed_tasks=self.completed_tasks,
            total_tasks=self.total_tasks,
            physical_calls=self.physical_calls,
            call_budget=self.call_budget,
            arm_id=self.arm_id,
            task_id=self.task_id,
        )

    def finish(self, *, mark_current_complete: bool = True) -> None:
        if mark_current_complete and self.current_trial_id is not None:
            self.completed_tasks = min(self.total_tasks, self.completed_tasks + 1)
            self.progress.update(
                completed_tasks=self.completed_tasks,
                total_tasks=self.total_tasks,
                physical_calls=self.physical_calls,
                call_budget=self.call_budget,
                arm_id=self.arm_id,
                task_id=self.task_id,
            )
        self.progress.finish()


class ProgressReportingAdapter:
    """Transparent model adapter wrapper that reports each physical S1 call."""

    def __init__(self, adapter: Any, tracker: S1ProgressTracker):
        self._adapter = adapter
        self._tracker = tracker

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]):
        self._tracker.call_started(str(context.get("trial_id") or "unknown"))
        return self._adapter.complete(messages, role=role, context=context)
