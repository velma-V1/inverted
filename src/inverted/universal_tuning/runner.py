from __future__ import annotations

from dataclasses import dataclass
import math
import shutil
import sys
import time
from typing import Any, Iterable

from .core import Observation, Profile
from .evidence import EvidenceStore
from .scheduler import ScheduledTrial
from .scoring import score_atomic_task
from .tasks import TaskPool


@dataclass(frozen=True)
class AdapterCompletion:
    responses: tuple[str, ...]
    latency_s: float
    output_tokens: int
    thinking_tokens: int
    physical_calls: int
    raw_calls: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class RunnerResult:
    physical_calls: int
    observation_count: int


def _format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return "--"
    value = int(round(seconds))
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_progress_line(*, done: int, total: int, elapsed_s: float, width: int) -> str:
    total = max(1, int(total))
    done = min(max(0, int(done)), total)
    left = max(0, total - done)
    pct = 100.0 * done / total
    rate = done / elapsed_s if done > 0 and elapsed_s > 0 else 0.0
    eta = left / rate if rate > 0 else None
    width = max(1, int(width))
    if width < 36:
        eta_short = "--" if eta is None else (f"{int(round(eta/60))}m" if eta >= 60 else f"{int(round(eta))}s")
        return f"{pct:.0f}% {done}d {left}l ETA {eta_short}"[:width]
    elapsed_text = _format_duration(elapsed_s)
    eta_text = _format_duration(eta)
    if width < 64:
        return f"{pct:3.0f}% {done} done {left} left ETA {eta_text}"[:width]
    suffix = f" {pct:5.1f}% | {done} done | {left} left | elapsed {elapsed_text} | ETA {eta_text}"
    bar_width = width - len(suffix) - 2
    if bar_width < 8:
        return suffix.strip()[:width]
    filled = min(bar_width, int(round(bar_width * done / total)))
    return ("[" + "#" * filled + "-" * (bar_width - filled) + "]" + suffix)[:width]


class ProgressReporter:
    def __init__(self, *, stream=None, width_provider=None, clock=None, persistent: bool = False) -> None:
        self.stream = stream or sys.stderr
        self.width_provider = width_provider or (lambda: shutil.get_terminal_size((100, 24)).columns)
        self.clock = clock or time.perf_counter
        self.persistent = bool(persistent)
        self.started_at = 0.0
        self._started = False
        self._projection: int | None = None

    def set_projection(self, total: int) -> None:
        self._projection = max(1, int(total))

    def _effective_total(self, done: int, total: int) -> int:
        if self._projection is None:
            return max(1, int(total))
        return max(int(done), int(total), self._projection)

    def start(self, *, done: int, total: int, started_at: float | None = None) -> None:
        if not self._started or not self.persistent:
            self.started_at = self.clock() if started_at is None else float(started_at)
            self._started = True
        self.update(done=done, total=total)

    def update(self, *, done: int, total: int) -> None:
        elapsed = max(0.0, self.clock() - self.started_at)
        effective_total = self._effective_total(done, total)
        line = format_progress_line(
            done=done, total=effective_total, elapsed_s=elapsed,
            width=int(self.width_provider()),
        )
        self.stream.write("\r" + line)
        self.stream.flush()

    def finish(self, *, done: int) -> None:
        self.update(done=done, total=max(1, done))
        if not self.persistent:
            self.stream.write("\n")
            self.stream.flush()

    def finalize(self, *, done: int) -> None:
        self._projection = max(1, int(done))
        self.update(done=done, total=max(1, done))
        self.stream.write("\n")
        self.stream.flush()


def _split_int(total: int, count: int) -> tuple[int, ...]:
    base, extra = divmod(max(0, int(total)), count)
    return tuple(base + (1 if index < extra else 0) for index in range(count))


class UniversalRunner:
    def __init__(
        self, root, pool: TaskPool, adapter: Any, manifest: dict[str, Any], *,
        max_physical_calls: int, progress: ProgressReporter | None = None,
    ) -> None:
        if manifest.get("task_pool_sha256") != pool.manifest_hash:
            raise ValueError("protocol manifest task-pool hash mismatch")
        self.pool = pool
        self.adapter = adapter
        self.max_physical_calls = int(max_physical_calls)
        self.progress = progress
        self.store = EvidenceStore(root, manifest)
        self._tasks = {task.task_id: task for task in pool.tasks}

    def _trial_tasks(self, trial: ScheduledTrial):
        try:
            return tuple(self._tasks[task_id] for task_id in trial.task_ids)
        except KeyError as exc:
            raise ValueError(f"scheduled task missing from frozen pool: {exc.args[0]}") from exc

    def run_trials(self, trials: Iterable[ScheduledTrial]) -> RunnerResult:
        requested = tuple(trials)
        completed = self.store.completed_trial_ids()
        pending = tuple(trial for trial in requested if trial.trial_id not in completed)
        used = self.store.physical_calls_used()
        projected = sum(trial.physical_calls for trial in pending)
        if used + projected > self.max_physical_calls:
            raise RuntimeError("universal tuning physical-call ceiling reached")
        if self.progress is not None:
            self.progress.start(done=used, total=max(1, used + projected))
        for trial in pending:
            tasks = self._trial_tasks(trial)
            completion = self.adapter.complete(tasks, trial.profile, trial.inference_seed)
            if len(completion.responses) != len(tasks):
                raise RuntimeError("adapter returned wrong response count")
            if int(completion.physical_calls) != trial.physical_calls:
                raise RuntimeError("adapter physical-call count does not match scheduled profile")
            observations = self._score_trial(trial, tasks, completion)
            self.store.commit_trial(
                trial_id=trial.trial_id, raw_calls=completion.raw_calls,
                responses=completion.responses, physical_calls=completion.physical_calls,
                observations=observations,
            )
            used += completion.physical_calls
            if self.progress is not None:
                self.progress.update(done=used, total=max(1, used + sum(t.physical_calls for t in pending if t.trial_id not in self.store.completed_trial_ids())))
        if self.progress is not None:
            self.progress.finish(done=used)
        return RunnerResult(used, len(self.store.observation_rows()))

    def _score_trial(self, trial: ScheduledTrial, tasks, completion: AdapterCompletion) -> tuple[Observation, ...]:
        count = len(tasks)
        output_parts = _split_int(completion.output_tokens, count)
        thinking_parts = _split_int(completion.thinking_tokens, count)
        latency_each = float(completion.latency_s) / count if count else 0.0
        raw_refs = tuple(f"{trial.trial_id}:call:{i}" for i in range(completion.physical_calls))
        observations = []
        for index, (task, response) in enumerate(zip(tasks, completion.responses)):
            score = score_atomic_task(task, response)
            observations.append(Observation(
                observation_id=f"{trial.trial_id}:{task.task_id}",
                batch_id=trial.batch_id, task_id=task.task_id, family=trial.family,
                stage=trial.stage, profile=trial.profile, inference_seed=trial.inference_seed,
                decision_reason=trial.decision_reason, semantic_pass=score.semantic_pass,
                contract_pass=score.contract_pass, completed=score.completed,
                semantic_quality=score.semantic_quality, contract_quality=score.contract_quality,
                latency_s=latency_each, output_tokens=output_parts[index],
                thinking_tokens=thinking_parts[index],
                physical_calls=completion.physical_calls if index == 0 else 0,
                response_text=response, failure_classes=score.failure_classes,
                raw_call_refs=raw_refs,
                metadata=(("trial_id", trial.trial_id),),
            ))
        return tuple(observations)
