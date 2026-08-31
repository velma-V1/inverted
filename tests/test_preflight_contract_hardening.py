from pathlib import Path

import httpx
import yaml

import inverted.cli as cli
from inverted.models import CompletionResult, OllamaAdapter
from inverted.telemetry import ModelCallRecord


def _ok_response(content: str) -> httpx.Response:
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
    return httpx.Response(
        200,
        request=request,
        json={
            "message": {"content": content},
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 10,
        },
    )


def _record(model: str, role: str, content: str) -> ModelCallRecord:
    attempt = {
        "attempt": 0,
        "status_code": 200,
        "content": content,
        "thinking": None,
        "prompt_eval_count": 10,
        "eval_count": 10,
        "done_reason": "stop",
    }
    return ModelCallRecord(
        call_id=f"{model}-{role}", run_id="preflight", trial_id=f"{model}-{role}", candidate_id=None,
        role=role, model=model, provider="ollama", start_ts="2026-08-31T00:00:00+00:00",
        end_ts="2026-08-31T00:00:01+00:00", latency_s=1.0, status_code=200,
        raw_provider_telemetry={
            "attempts": [attempt], "content": content, "thinking": None,
            "prompt_eval_count": 10, "eval_count": 10, "done_reason": "stop",
        },
        response=content,
    )


def test_ollama_executor_uses_exact_json_schema_not_loose_json_mode(monkeypatch):
    payloads = []

    def fake_post(*args, **kwargs):
        payloads.append(kwargs["json"])
        return _ok_response('{"actions":[]}')

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="phi4-mini:3.8b", format_json=True, max_retries=0)
    model.complete([{"role": "user", "content": "x"}], role="executor", context={})

    schema = payloads[0]["format"]
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert schema["required"] == ["actions"]
    assert schema["additionalProperties"] is False
    actions = schema["properties"]["actions"]
    assert actions["type"] == "array"
    assert actions["maxItems"] == 64
    item = actions["items"]
    assert set(item["required"]) == {"op", "path"}
    assert item["additionalProperties"] is False
    assert set(item["properties"]["op"]["enum"]) == {"set", "resolve", "delete"}
    assert set(item["properties"]["value"]["type"]) == {"string", "number", "boolean", "object", "array", "null"}


def test_ollama_auditor_uses_exact_json_schema(monkeypatch):
    payloads = []

    def fake_post(*args, **kwargs):
        payloads.append(kwargs["json"])
        return _ok_response('{"accept":true,"failed_requirements":[],"reason":"ok"}')

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaAdapter(model="llama3.1:8b", format_json=True, max_retries=0)
    model.complete([{"role": "user", "content": "x"}], role="auditor", context={})

    schema = payloads[0]["format"]
    assert isinstance(schema, dict)
    assert set(schema["required"]) == {"accept", "failed_requirements", "reason"}
    assert schema["properties"]["accept"]["type"] == "boolean"
    assert schema["properties"]["failed_requirements"]["maxItems"] == 64
    assert schema["additionalProperties"] is False


def test_preflight_parser_failure_is_model_evidence_not_campaign_abort():
    class ParserWeakModel:
        provider = "ollama"
        model = "parser-weak"
        context_limit = 8192
        think = False
        format_json = True

        def complete(self, messages, *, role, context):
            content = "{" if role.endswith("executor") else '{"accept":true,"failed_requirements":[],"reason":"ok"}'
            return CompletionResult(content, _record(self.model, role, content), {})

        def unload(self):
            return {}

    rows = cli._preflight_models([ParserWeakModel()], cells_per_model=12, max_generation_censored=0)
    assert len(rows) == 1
    assert rows[0]["executor_parse_ok"] is False
    assert rows[0]["executor_parse_failures"] == 6
    assert rows[0]["auditor_parse_ok"] is True
    assert rows[0]["auditor_parse_failures"] == 0


def test_cli_preflight_failure_returns_dedicated_code_without_traceback(tmp_path, monkeypatch, capsys):
    cfg = {
        "benchmark": {"decisive": False},
        "models": [{"provider": "ollama", "model": "phi4-mini:3.8b", "format_json": True}],
        "report": {"capture_content": True, "include_raw_rows": True},
    }
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def fail_preflight(*args, **kwargs):
        raise ValueError("preflight executor JSON contract failed for phi4-mini:3.8b")

    monkeypatch.setattr(cli, "_preflight_models", fail_preflight)
    code = cli.main(["--config", str(path), "--output-dir", str(tmp_path / "runs"), "--run-id", "pf-fail"])
    out = capsys.readouterr().out
    assert code == 2
    assert "PREFLIGHT_FAILURE" in out
    assert "phi4-mini:3.8b" in out
    assert "Traceback" not in out


def test_wrapper_surfaces_terminal_failure_instead_of_throwing_generic_exit_code():
    text = Path("scripts/run-overnight-handoff.ps1").read_text(encoding="utf-8")
    assert "Get-Content -Path $TerminalLog -Tail" in text
    assert "ROOT FAILURE FROM TERMINAL LOG" in text
    assert "exit $WatcherExit" in text
    assert 'throw "Overnight handoff exited with code $WatcherExit' not in text
