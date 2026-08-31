import pytest
from inverted.models import MockModelAdapter, OllamaAdapter, OpenAICompatibleAdapter


def test_mock_is_deterministic():
    model = MockModelAdapter(model="mock-1", seed=9)
    a = model.complete([{"role": "user", "content": "x"}], role="auditor", context={"mock_text": '{"accept": true}'})
    b = model.complete([{"role": "user", "content": "x"}], role="auditor", context={"mock_text": '{"accept": true}'})
    assert a.text == b.text
    assert a.record.input_tokens == b.record.input_tokens
    assert a.record.output_tokens == b.record.output_tokens


def test_mock_records_role_and_usage():
    model = MockModelAdapter(model="mock-1", seed=1)
    result = model.complete([{"role": "user", "content": "hello world"}], role="executor", context={"mock_text": "ok", "run_id":"r", "trial_id":"t"})
    assert result.record.role == "executor"
    assert result.record.provider == "mock"
    assert result.record.total_tokens == result.record.input_tokens + result.record.output_tokens
    assert result.record.latency_s >= 0


def test_real_adapters_do_not_have_mock_fallback():
    openai = OpenAICompatibleAdapter(model="x", base_url="http://127.0.0.1:1", api_key=None, timeout_s=0.01)
    ollama = OllamaAdapter(model="x", base_url="http://127.0.0.1:1", timeout_s=0.01)
    for adapter in (openai, ollama):
        with pytest.raises(Exception):
            adapter.complete([{"role":"user","content":"x"}], role="auditor", context={})
