from inverted.models import MockModelAdapter
from inverted.report import render_report
from inverted.runner import ExperimentConfig, run_experiment
from inverted.statistics import aggregate_trials
from inverted.validation import VALIDATION_SCOPE
from inverted.verdict import decide_verdict


def _render(cfg):
    result = run_experiment(cfg, [MockModelAdapter(model="m", executor_accuracy=0.6, auditor_accuracy=0.9)], run_id="report")
    summary = aggregate_trials(result.trials, 100, 2)
    verdict = decide_verdict(summary, cfg)
    return render_report(summary, verdict, result, {"python":"x"}, {"events":"events.jsonl"}, include_raw_rows=True)


def test_report_contains_all_required_metric_families():
    cfg = ExperimentConfig(families=("state", "policy", "reconciliation"), complexities=(1,), qualities=(0.4,0.8), seeds=(1,2), epochs=1, decisive=False)
    text = _render(cfg)
    required = [
        "VERDICT", "D - A", "95%", "CROSSOVER", "A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED",
        "TP", "TN", "FP", "FN", "TOKENS", "TOKENS/SEC", "LATENCY", "P50", "P90", "P95", "P99", "TTFT",
        "MODEL CALLS", "RETRIES", "TIMEOUTS", "PARSER", "COST", "FAILURE TAXONOMY", "MODEL SLICES", "FAMILY SLICES",
        "COMPLEXITY SLICES", "QUALITY SLICES", "PROVENANCE", "RAW ARTIFACTS", "FULL TRIAL LEDGER", "FULL MODEL CALL LEDGER"
    ]
    upper = text.upper()
    for marker in required:
        assert marker in upper, marker


def test_validation_report_is_unambiguously_labeled_not_architecture_evidence():
    cfg = ExperimentConfig(
        families=("state",), complexities=(1,), qualities=(0.8,), seeds=(1,), epochs=1, decisive=False,
        metadata={"evidence_scope": VALIDATION_SCOPE},
    )
    text = _render(cfg)
    assert f"EVIDENCE SCOPE: {VALIDATION_SCOPE}" in text
