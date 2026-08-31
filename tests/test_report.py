from inverted.models import MockModelAdapter
from inverted.report import render_report
from inverted.runner import ExperimentConfig, run_experiment
from inverted.statistics import aggregate_trials
from inverted.verdict import decide_verdict


def test_report_contains_all_required_metric_families():
    cfg = ExperimentConfig(families=("state", "policy", "reconciliation"), complexities=(1,), qualities=(0.4,0.8), seeds=(1,2), epochs=1, decisive=False)
    result = run_experiment(cfg, [MockModelAdapter(model="m", executor_accuracy=0.6, auditor_accuracy=0.9)], run_id="report")
    summary = aggregate_trials(result.trials, 100, 2)
    verdict = decide_verdict(summary, cfg)
    text = render_report(summary, verdict, result, {"python":"x"}, {"events":"events.jsonl"}, include_raw_rows=True)
    required = [
        "VERDICT", "D - A", "95%", "CROSSOVER", "A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED",
        "TP", "TN", "FP", "FN", "TOKENS", "TOKENS/SEC", "LATENCY", "P50", "P90", "P95", "P99", "TTFT",
        "MODEL CALLS", "RETRIES", "TIMEOUTS", "PARSER", "COST", "FAILURE TAXONOMY", "MODEL SLICES", "FAMILY SLICES",
        "COMPLEXITY SLICES", "QUALITY SLICES", "PROVENANCE", "RAW ARTIFACTS", "FULL TRIAL LEDGER", "FULL MODEL CALL LEDGER"
    ]
    upper = text.upper()
    for marker in required:
        assert marker in upper, marker
