from __future__ import annotations

from datetime import datetime, timedelta
import shutil
import sys
import time
from typing import Any, TextIO


def _duration(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _compact_duration(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes:02d}:{secs:02d}"


class InPlaceS2Progress:
    """Terminal-width-aware S2 progress with non-causal ETA telemetry."""

    def __init__(self, *, stream: TextIO | None = None, width: int = 16):
        self.stream = stream if stream is not None else sys.stdout
        self.width = min(20, max(8, int(width)))
        self._last_width = 0
        self._finished = False
        self._started = time.monotonic()

    def update(
        self,
        *,
        completed_trials: int,
        total_trials: int,
        physical_calls: int,
        call_budget: int,
        arm_id: str = "",
        phase: str = "",
    ) -> None:
        if self._finished:
            return
        total = max(1, int(total_trials))
        completed = min(total, max(0, int(completed_trials)))
        calls_total = max(0, int(call_budget))
        calls_done = max(0, int(physical_calls))
        ratio = min(1.0, calls_done / calls_total) if calls_total > 0 else completed / total
        percent = ratio * 100.0
        elapsed = max(0.0, time.monotonic() - self._started)
        if ratio > 0:
            remaining = max(0.0, elapsed * (1.0 - ratio) / ratio)
            eta = datetime.now().astimezone() + timedelta(seconds=remaining)
            left = _duration(remaining)
            eta_text = eta.strftime("%H:%M:%S")
            compact_left = _compact_duration(remaining)
            compact_eta = eta.strftime("%H:%M")
        else:
            left = "--:--:--"
            eta_text = "--:--:--"
            compact_left = "--:--"
            compact_eta = "--:--"

        columns = max(40, int(shutil.get_terminal_size(fallback=(112, 24)).columns))
        max_chars = max(39, columns - 1)
        arm = str(arm_id).strip()
        phase_text = str(phase).strip()
        if max_chars >= 105:
            filled = min(self.width, int(self.width * ratio))
            bar = "#" * filled + "-" * (self.width - filled)
            line = (
                f"S2 [{bar}] {percent:5.1f}% {completed}/{total} | {calls_done}/{calls_total} calls | "
                f"elapsed {_duration(elapsed)} | left {left} | ETA {eta_text}"
            )
            suffix = "/".join(value for value in (arm[:8], phase_text[:8]) if value)
            if suffix:
                line += f" | {suffix}"
        else:
            bar_width = max(4, min(6, max_chars - 60))
            filled = min(bar_width, int(bar_width * ratio))
            bar = "#" * filled + "-" * (bar_width - filled)
            arm_short = arm.replace("S2-", "")[:3]
            line = (
                f"S2[{bar}] {percent:.1f}% {completed}/{total} {calls_done}/{calls_total} "
                f"elapsed{_compact_duration(elapsed)} left{compact_left} ETA{compact_eta}"
            )
            if arm_short:
                line += f" {arm_short}"

        line = line[:max_chars]
        pad_width = min(max_chars, max(self._last_width, len(line)))
        self.stream.write("\r" + line.ljust(pad_width))
        self.stream.flush()
        self._last_width = len(line)

    def finish(self) -> None:
        if self._finished:
            return
        self.stream.write("\n")
        self.stream.flush()
        self._finished = True


class S2ProgressTracker:
    def __init__(self, progress: InPlaceS2Progress, *, total_trials: int, call_budget: int):
        self.progress = progress
        self.total_trials = max(0, int(total_trials))
        self.call_budget = max(0, int(call_budget))
        self.current_trial_id: str | None = None
        self.completed_trials = 0
        self.physical_calls = 0
        self.arm_id = ""
        self.phase = ""

    @staticmethod
    def _arm(trial_id: str) -> str:
        marker = "-S2-B"
        index = trial_id.rfind(marker)
        if index < 0:
            return ""
        suffix = trial_id[index + 1 :]
        return suffix.split("-", 2)[0] + "-" + suffix.split("-", 2)[1] if suffix.count("-") >= 1 else suffix

    def call_started(self, trial_id: str, *, phase: str = "") -> None:
        trial = str(trial_id or "unknown")
        if self.current_trial_id is not None and trial != self.current_trial_id:
            self.completed_trials = min(self.total_trials, self.completed_trials + 1)
        self.current_trial_id = trial
        self.arm_id = self._arm(trial)
        self.phase = str(phase or "")
        self.physical_calls += 1
        self.progress.update(
            completed_trials=self.completed_trials,
            total_trials=self.total_trials,
            physical_calls=self.physical_calls,
            call_budget=self.call_budget,
            arm_id=self.arm_id,
            phase=self.phase,
        )

    def finish(self, *, mark_current_complete: bool = True) -> None:
        if mark_current_complete and self.current_trial_id is not None:
            self.completed_trials = min(self.total_trials, self.completed_trials + 1)
            self.progress.update(
                completed_trials=self.completed_trials,
                total_trials=self.total_trials,
                physical_calls=self.physical_calls,
                call_budget=self.call_budget,
                arm_id=self.arm_id,
                phase=self.phase,
            )
        self.progress.finish()


class ProgressReportingAdapter:
    """Transparent adapter wrapper; reporting cannot alter model inputs or output."""

    def __init__(self, adapter: Any, tracker: S2ProgressTracker):
        self._adapter = adapter
        self._tracker = tracker

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]):
        trial = str(context.get("trial_id") or "unknown")
        phase = "repair" if role == "repairer" else "execute"
        self._tracker.call_started(trial, phase=phase)
        return self._adapter.complete(messages, role=role, context=context)
