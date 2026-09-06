import json

import pytest
from inverted.harvest_d.models import OllamaChatAdapter
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


def test_complete_request_bytes_sends_exact_body_in_one_opener_call():
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self):
            return json.dumps({"model": "m", "message": {"content": "ok"}}).encode()

    def opener(request, *, timeout):
        calls.append((request.data, timeout))
        return Response()

    adapter = OllamaChatAdapter("m", opener=opener, timeout=17)
    body = b'{"exact":"bytes", "spacing":true}'
    response = adapter.complete_request_bytes(body)

    assert response.text == "ok"
    assert calls == [(body, 17)]


def test_complete_request_bytes_rejects_response_without_model_identity():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self):
            return json.dumps({"message": {"content": "ok"}}).encode()

    adapter = OllamaChatAdapter("m", opener=lambda request, *, timeout: Response())

    with pytest.raises(ValueError, match="model"):
        adapter.complete_request_bytes(b'{}')


@pytest.mark.parametrize("raw", [
    b'{"model":"wrong","model":"m","message":{"content":"ok"}}',
    b'{"model":"m","total_duration":NaN,"message":{"content":"ok"}}',
    b'{"model":"m","total_duration":Infinity,"message":{"content":"ok"}}',
])
def test_complete_request_bytes_rejects_noncanonical_response_json(raw):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return raw

    adapter = OllamaChatAdapter("m", opener=lambda request, *, timeout: Response())

    with pytest.raises(ValueError):
        adapter.complete_request_bytes(b'{}')


def test_harvest_d_ollama_adapter_can_emit_explicit_non_thinking_request():
    adapter = OllamaChatAdapter("m", think=False)
    payload = json.loads(adapter.request_bytes("answer", "system").decode("utf-8"))
    assert payload["think"] is False
