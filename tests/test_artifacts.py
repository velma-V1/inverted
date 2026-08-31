import csv, json
from pathlib import Path
from inverted.artifacts import ArtifactWriter, collect_provenance
from inverted.models import MockModelAdapter
from inverted.runner import ExperimentConfig, run_experiment
from inverted.statistics import aggregate_trials
from inverted.verdict import decide_verdict


def test_artifact_writer_creates_complete_machine_readable_bundle(tmp_path):
    cfg = ExperimentConfig(families=("state",), complexities=(1,), qualities=(0.8,), seeds=(1,), epochs=1, decisive=False)
    result = run_experiment(cfg, [MockModelAdapter(model="m")], run_id="artifact-test")
    summary = aggregate_trials(result.trials, 100, 1)
    verdict = decide_verdict(summary, cfg)
    writer = ArtifactWriter(tmp_path / "artifact-test")
    paths = writer.write_all(result, summary, verdict, collect_provenance(), include_raw_rows=True)
    required = {"events.jsonl","model_calls.jsonl","trials.csv","trials.jsonl","failures.csv","summary.json","summary.csv","report.txt","config.json","provenance.json"}
    assert required == {Path(p).name for p in paths.values()}
    for p in paths.values():
        assert Path(p).exists()
    json.loads((tmp_path / "artifact-test" / "summary.json").read_text())
    rows = list(csv.DictReader((tmp_path / "artifact-test" / "trials.csv").open()))
    assert len(rows) == len(result.trials)


def test_model_call_jsonl_has_every_normalized_record(tmp_path):
    cfg = ExperimentConfig(families=("state",), complexities=(1,), qualities=(0.8,), seeds=(1,), epochs=1, arms=("A_DIRECT","D_INVERTED"))
    result = run_experiment(cfg, [MockModelAdapter(model="m")], run_id="calls")
    summary = aggregate_trials(result.trials, 50, 1)
    verdict = decide_verdict(summary, cfg)
    ArtifactWriter(tmp_path / "calls").write_all(result, summary, verdict, collect_provenance(), include_raw_rows=True)
    lines = [json.loads(x) for x in (tmp_path / "calls" / "model_calls.jsonl").read_text().splitlines() if x]
    assert len(lines) == len(result.model_calls)
    assert {"call_id","role","latency_s","input_tokens","output_tokens","total_tokens","generated_tokens_per_s","raw_usage"} <= set(lines[0])


def test_trial_and_event_ledgers_have_exact_reconstructable_cardinality(tmp_path):
    cfg = ExperimentConfig(
        families=("state", "policy"), complexities=(1,), qualities=(0.2, 0.8), seeds=(1, 2), epochs=1,
        arms=("A_DIRECT", "C_SYSTEM", "D_INVERTED", "F_ORACLE_AUDITOR"), max_tokens_per_trial=10000,
    )
    result = run_experiment(cfg, [MockModelAdapter(model="m", auditor_accuracy=0.9)], run_id="ledger-count")
    summary = aggregate_trials(result.trials, 50, 1)
    verdict = decide_verdict(summary, cfg)
    run_dir = tmp_path / "ledger-count"
    ArtifactWriter(run_dir).write_all(result, summary, verdict, collect_provenance(), include_raw_rows=True)

    trials_jsonl = [json.loads(x) for x in (run_dir / "trials.jsonl").read_text().splitlines() if x]
    events = [json.loads(x) for x in (run_dir / "events.jsonl").read_text().splitlines() if x]
    model_calls = [json.loads(x) for x in (run_dir / "model_calls.jsonl").read_text().splitlines() if x]

    candidate_events = sum(len(t.candidate_events) for t in result.trials)
    assert len(trials_jsonl) == len(result.trials)
    assert len(model_calls) == len(result.model_calls)
    assert sum(event["event"] == "trial_terminal" for event in events) == len(result.trials)
    assert sum(event["event"] == "candidate" for event in events) == candidate_events
    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "run_ended"
