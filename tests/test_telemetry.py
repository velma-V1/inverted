from inverted.telemetry import ModelCallRecord


def test_model_call_record_calculates_throughput():
    rec = ModelCallRecord(
        call_id="c", run_id="r", trial_id="t", candidate_id=None,
        role="executor", model="m", provider="mock",
        start_ts="s", end_ts="e", latency_s=2.0,
        input_tokens=10, output_tokens=20, total_tokens=30,
        eval_duration_s=1.0,
    )
    assert rec.generated_tokens_per_s == 20.0
    assert rec.end_to_end_tokens_per_s == 10.0


def test_unavailable_telemetry_stays_none():
    rec = ModelCallRecord(
        call_id="c", run_id="r", trial_id="t", candidate_id=None,
        role="auditor", model="m", provider="mock",
        start_ts="s", end_ts="e", latency_s=1.0,
    )
    assert rec.input_tokens is None
    assert rec.output_tokens is None
    assert rec.ttft_s is None
    assert rec.generated_tokens_per_s is None
    assert rec.cost_usd is None
