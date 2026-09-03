from inverted.harvest_d.d3_executor import (
    D3CallExecutor,
    D3CallPlan,
    run_reproducibility_block,
)
from inverted.harvest_d.d3_store import D3EvidenceStore
from inverted.harvest_d.models import ModelResponse


class CountingAdapter:
    model_id = "fake:model"

    def __init__(self, text: str = '{"answer":"ok"}'):
        self.text = text
        self.calls = 0

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            text=self.text,
            model=self.model_id,
            input_tokens=7,
            output_tokens=3,
            latency_ms=12.5,
            raw={
                "message": {"content": self.text},
                "done_reason": "stop",
                "load_duration": 123,
                "unknown_future_field": "preserve-me",
            },
        )


def _plan(case_id: str = "case-a") -> D3CallPlan:
    return D3CallPlan(
        case_id=case_id,
        prompt="Return JSON only.",
        system="You are under D3 measurement.",
        information_packet={"packet_id": "p1", "fields": ["I1", "I2"]},
        scheduler_event={"candidate_id": case_id, "selection_mode": "ADAPTIVE"},
    )


def test_executor_calls_adapter_once_even_when_response_is_malformed(tmp_path):
    adapter = CountingAdapter("not json")
    store = D3EvidenceStore(tmp_path)
    result = D3CallExecutor(store=store).execute_once(_plan(), adapter)
    assert adapter.calls == 1
    assert result.failure_class == "FORMAT_OR_SCHEMA"
    assert store.capture_status(result.physical_model_call_id).admissibility.value == "ADMISSIBLE"


def test_executor_preserves_exact_request_response_and_previous_call_link(tmp_path):
    store = D3EvidenceStore(tmp_path)
    executor = D3CallExecutor(store=store)
    adapter = CountingAdapter()
    first = executor.execute_once(_plan("a"), adapter)
    second = executor.execute_once(_plan("b"), adapter)

    normalized = store.normalized_call(second.physical_model_call_id)
    assert normalized["previous_physical_model_call_id"] == first.physical_model_call_id
    assert store.raw_request(second.physical_model_call_id)["messages"]
    payload = store.raw_response(second.physical_model_call_id)["payload"]
    assert payload["unknown_future_field"] == "preserve-me"
    assert payload["load_duration"] == 123


def test_executor_records_generation_and_runtime_metadata_without_dropping_unknown_fields(tmp_path):
    store = D3EvidenceStore(tmp_path)
    result = D3CallExecutor(store=store).execute_once(_plan(), CountingAdapter())
    row = store.normalized_call(result.physical_model_call_id)
    assert row["input_tokens"] == 7
    assert row["output_tokens"] == 3
    assert row["latency_ms"] == 12.5
    assert row["runtime_extras"]["unknown_future_field"] == "preserve-me"


def test_reproducibility_block_defaults_to_24_physical_calls(tmp_path):
    store = D3EvidenceStore(tmp_path)
    executor = D3CallExecutor(store=store)
    small = CountingAdapter()
    qwen = CountingAdapter()
    plans = [_plan(f"case-{i}") for i in range(4)]

    result = run_reproducibility_block(
        executor,
        adapters=(small, qwen),
        plans=plans,
        repetitions=3,
    )
    assert result.calls_used == 24
    assert small.calls == 12
    assert qwen.calls == 12
    assert len(result.observations) == 24
