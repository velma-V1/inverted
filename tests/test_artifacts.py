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
