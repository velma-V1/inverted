import json
from dataclasses import asdict
from pathlib import Path

import pytest

from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.runner import (
    AdapterCompletion,
    ProgressReporter,
    UniversalRunner,
    format_progress_line,
)
from inverted.universal_tuning.scheduler import AdaptiveScheduler, ModelMetadata
from inverted.universal_tuning.tasks import build_qwen_task_pool


class SyntheticAdapter:
    def __init__(self):
        self.calls = []

    def complete(self, tasks, profile, seed):
        self.calls.append((tuple(t.task_id for t in tasks), profile, seed))
        responses = tuple(json.dumps({"answer": task.expected}) for task in tasks)
        physical = 2 if profile.thinking else 1
        return AdapterCompletion(
            responses=responses, latency_s=0.25 * physical,
            output_tokens=10 * len(tasks), thinking_tokens=profile.thinking_budget,
            physical_calls=physical, raw_calls=tuple({"call": i} for i in range(physical)),
        )


def _setup(tmp_path):
    pool = build_qwen_task_pool(seed=44, per_family=120)
    scheduler = AdaptiveScheduler(pool, ModelMetadata())
    trials = scheduler.paired_trials(
        family="EXTRACTION", stage="gate",
        baseline=Profile(0, 0.7), candidate=Profile(1024, 1.0),
        atomic_count=40, task_offset=0, decision_reason="GATE",
    )
    manifest = {
        "protocol_version": 2,
        "task_pool_sha256": pool.manifest_hash,
        "model": "synthetic",
    }
    return pool, trials, manifest


def test_runner_executes_paired_batches_and_persists_decision_reason(tmp_path):
    pool, trials, manifest = _setup(tmp_path)
    adapter = SyntheticAdapter()
    result = UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=100).run_trials(trials)
    assert result.physical_calls == 24
    assert len(adapter.calls) == 16
    rows = [json.loads(line) for line in (tmp_path / "atomic_observations.jsonl").read_text().splitlines()]
    assert len(rows) == 80
    assert {row["decision_reason"] for row in rows} == {"GATE"}
    assert all(row["semantic_pass"] for row in rows)


def test_resume_skips_completed_trials_without_duplicate_calls(tmp_path):
    pool, trials, manifest = _setup(tmp_path)
    adapter = SyntheticAdapter()
    runner = UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=100)
    first = runner.run_trials(trials[:4])
    before = (tmp_path / "atomic_observations.jsonl").read_bytes()
    calls_before = len(adapter.calls)
    second = runner.run_trials(trials[:4])
    assert first.physical_calls == second.physical_calls
    assert len(adapter.calls) == calls_before
    assert (tmp_path / "atomic_observations.jsonl").read_bytes() == before


def test_manifest_hash_mismatch_is_rejected_before_calls(tmp_path):
    pool, trials, manifest = _setup(tmp_path)
    adapter = SyntheticAdapter()
    UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=100)
    bad = dict(manifest, model="different")
    with pytest.raises(ValueError, match="manifest"):
        UniversalRunner(tmp_path, pool, adapter, bad, max_physical_calls=100)
    assert adapter.calls == []


def test_hard_call_ceiling_rejects_batch_before_any_new_call(tmp_path):
    pool, trials, manifest = _setup(tmp_path)
    adapter = SyntheticAdapter()
    runner = UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=23)
    with pytest.raises(RuntimeError, match="ceiling"):
        runner.run_trials(trials)
    assert adapter.calls == []


def test_evidence_is_append_only_when_more_trials_are_added(tmp_path):
    pool, trials, manifest = _setup(tmp_path)
    adapter = SyntheticAdapter()
    runner = UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=100)
    runner.run_trials(trials[:2])
    first_obs = (tmp_path / "atomic_observations.jsonl").read_bytes()
    first_raw = (tmp_path / "raw_calls.jsonl").read_bytes()
    runner.run_trials(trials[:4])
    assert (tmp_path / "atomic_observations.jsonl").read_bytes().startswith(first_obs)
    assert (tmp_path / "raw_calls.jsonl").read_bytes().startswith(first_raw)


def test_scheduler_batch_seeds_remain_distinct_through_runner(tmp_path):
    pool, trials, manifest = _setup(tmp_path)
    adapter = SyntheticAdapter()
    UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=100).run_trials(trials[:6])
    seeds = [seed for _, _, seed in adapter.calls]
    assert seeds[0] == seeds[1]
    assert seeds[2] == seeds[3]
    assert seeds[0] != seeds[2]


def test_progress_line_is_terminal_width_responsive():
    wide = format_progress_line(done=24, total=60, elapsed_s=120, width=110)
    narrow = format_progress_line(done=24, total=60, elapsed_s=120, width=34)
    assert len(wide) <= 110 and "24" in wide and "36" in wide
    assert len(narrow) <= 34 and "24" in narrow and "36" in narrow


def test_progress_reporter_rechecks_width_each_update():
    import io
    widths = iter((100, 32))
    stream = io.StringIO()
    reporter = ProgressReporter(stream=stream, width_provider=lambda: next(widths), clock=lambda: 10.0)
    reporter.start(done=0, total=60, started_at=0.0)
    reporter.update(done=24, total=60)
    lines = stream.getvalue().split("\r")
    assert len(lines[-1]) <= 32


def test_persistent_progress_uses_campaign_projection_and_only_newlines_at_finalize():
    import io
    stream = io.StringIO()
    reporter = ProgressReporter(
        stream=stream, width_provider=lambda: 100, clock=lambda: 10.0,
        persistent=True,
    )
    reporter.set_projection(100)
    reporter.start(done=0, total=24, started_at=0.0)
    reporter.set_projection(80)
    reporter.update(done=24, total=30)
    assert "24 done" in stream.getvalue()
    assert "56 left" in stream.getvalue()
    before = stream.getvalue()
    reporter.finish(done=24)
    assert not stream.getvalue().endswith("\n")
    reporter.finalize(done=80)
    assert stream.getvalue().endswith("\n")
    assert len(stream.getvalue()) > len(before)


def test_model_completion_failure_is_recorded_and_later_trials_continue(tmp_path):
    class FirstBatchEmptyAdapter(SyntheticAdapter):
        def complete(self, tasks, profile, seed):
            self.calls.append((tuple(t.task_id for t in tasks), profile, seed))
            physical = 2 if profile.thinking else 1
            responses = tuple("" for _ in tasks) if len(self.calls) == 1 else tuple(
                json.dumps({"answer": task.expected}) for task in tasks
            )
            return AdapterCompletion(
                responses=responses, latency_s=0.01, output_tokens=0,
                thinking_tokens=profile.thinking_budget, physical_calls=physical,
                raw_calls=tuple({"call": i, "empty": not bool(responses[0])} for i in range(physical)),
            )

    pool, trials, manifest = _setup(tmp_path)
    adapter = FirstBatchEmptyAdapter()
    result = UniversalRunner(tmp_path, pool, adapter, manifest, max_physical_calls=100).run_trials(trials[:4])
    assert len(adapter.calls) == 4
    assert result.physical_calls > 0
    rows = [json.loads(line) for line in (tmp_path / "atomic_observations.jsonl").read_text().splitlines()]
    persisted_profile = json.loads(json.dumps(asdict(trials[0].profile)))
    first_batch = [
        row for row in rows
        if row["batch_id"] == trials[0].batch_id
        and row["profile"] == persisted_profile
    ]
    assert len(first_batch) == 5
    assert all(not row["completed"] for row in first_batch)
    assert all("COMPLETION_FAIL" in row["failure_classes"] for row in first_batch)
    assert any(row["semantic_pass"] for row in rows if row["batch_id"] != trials[0].batch_id)
