from inverted.arms import TrialRecord
from inverted.statistics import aggregate_trials, bootstrap_rate_difference, estimate_crossover
from inverted.telemetry import ModelCallRecord


def trial(arm, success, quality=0.8, family="state", model="m", seed=1, latency=1.0, tokens=30, catastrophic=False, task_id=None):
    call = ModelCallRecord(
        call_id=f"c-{arm}-{seed}", run_id="r", trial_id=f"t-{arm}-{seed}-{quality}-{family}", candidate_id=None,
        role="auditor" if arm=="D_INVERTED" else "executor", model=model, provider="mock", start_ts="s", end_ts="e", latency_s=latency,
        input_tokens=10, output_tokens=tokens-10, total_tokens=tokens, eval_duration_s=max(latency/2, 0.001), ttft_s=0.1,
        parse_success=True,
    )
    return TrialRecord(
        trial_id=f"t-{arm}-{seed}-{quality}-{family}", run_id="r", task_id=task_id or f"task-{seed}-{quality}-{family}", family=family, complexity=2,
        arm=arm, model=model, provider="mock", seed=seed, epoch=0, configured_executor_quality=quality,
        success=success, catastrophic=catastrophic, requirement_accuracy=1.0 if success else 0.5,
        terminal_status="SUCCESS" if success else "FAILED", total_tokens=tokens, total_input_tokens=10, total_output_tokens=tokens-10,
        total_model_latency_s=latency, end_to_end_latency_s=latency+0.2, audit_tp=1 if arm=="D_INVERTED" and success else 0,
        audit_fp=1 if arm=="D_INVERTED" and not success else 0, failure_reasons=() if success else ("fault:wrong_value",), model_calls=[call]
    )


def test_aggregate_contains_accuracy_tokens_latency_confusion_and_failures():
    trials = [trial("A_DIRECT", True, seed=1), trial("A_DIRECT", False, seed=2), trial("D_INVERTED", True, seed=1), trial("D_INVERTED", False, seed=2)]
    s = aggregate_trials(trials)
    assert s["by_arm"]["A_DIRECT"]["success_rate"] == 0.5
    assert s["by_arm"]["A_DIRECT"]["total_tokens"] == 60
    assert s["by_arm"]["A_DIRECT"]["model_call_latency_s"]["p50"] == 1.0
    assert s["by_arm"]["D_INVERTED"]["auditor"]["tp"] == 1
    assert s["by_arm"]["D_INVERTED"]["auditor"]["fp"] == 1
    assert s["failure_taxonomy"]["fault:wrong_value"] == 2
    assert "tokens_per_success" in s["by_arm"]["A_DIRECT"]
    assert "generated_tokens_per_s" in s["by_arm"]["A_DIRECT"]


def test_bootstrap_difference_is_seeded():
    trials = []
    for i in range(20):
        trials += [trial("A_DIRECT", i < 8, seed=i), trial("D_INVERTED", i < 16, seed=i)]
    a = bootstrap_rate_difference(trials, "D_INVERTED", "A_DIRECT", 500, 123)
    b = bootstrap_rate_difference(trials, "D_INVERTED", "A_DIRECT", 500, 123)
    assert a == b
    assert a["estimate"] > 0
    assert a["lower"] > 0
    assert a["n_clusters"] == 20


def test_bootstrap_clusters_repeated_quality_and_model_rows_by_task():
    trials = []
    qualities = [0.2, 0.4, 0.6, 0.8, 0.95]
    models = ["m1", "m2", "m3"]
    for i in range(6):
        task_id = f"independent-task-{i}"
        for model in models:
            for quality in qualities:
                trials += [
                    trial("A_DIRECT", False, quality=quality, model=model, seed=i, task_id=task_id),
                    trial("D_INVERTED", True, quality=quality, model=model, seed=i, task_id=task_id),
                ]
    result = bootstrap_rate_difference(trials, "D_INVERTED", "A_DIRECT", 200, 99)
    assert result["n_pairs"] == 6 * len(models) * len(qualities)
    assert result["n_clusters"] == 6
    assert result["estimate"] == 1.0


def test_aggregate_exposes_independent_task_cluster_count():
    trials = []
    for i in range(4):
        task_id = f"task-{i}"
        for quality in [0.2, 0.8]:
            trials += [
                trial("A_DIRECT", False, quality=quality, seed=i, task_id=task_id),
                trial("D_INVERTED", True, quality=quality, seed=i, task_id=task_id),
            ]
    summary = aggregate_trials(trials, bootstrap_samples=100, bootstrap_seed=1)
    assert summary["primary"]["independent_task_clusters"] == 4


def test_crossover_finds_first_quality_where_inversion_wins():
    trials = []
    for q, d_successes in [(0.2, 2), (0.4, 4), (0.6, 8), (0.8, 9)]:
        for i in range(10):
            trials += [trial("A_DIRECT", i < 5, quality=q, seed=i), trial("D_INVERTED", i < d_successes, quality=q, seed=i)]
    c = estimate_crossover(trials)
    assert c["crossover_quality"] == 0.6
