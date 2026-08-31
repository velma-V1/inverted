from pathlib import Path

import httpx
import yaml

import inverted.cli as cli
from inverted.models import OllamaAdapter


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
    item = actions["items"]
    assert set(item["required"]) == {"op", "path"}
    assert item["additionalProperties"] is False


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
    assert schema["additionalProperties"] is False


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


def test_zero_trial_resume_archives_stale_preflight_logs(tmp_path):
    checkpoint_path = tmp_path / "run.checkpoint.jsonl"
    failure_log = tmp_path / "run.call-failures.jsonl"
    preflight_log = tmp_path / "run.preflight-model-calls.jsonl"
    failure_log.write_text("old failure\n", encoding="utf-8")
    preflight_log.write_text("old preflight\n", encoding="utf-8")

    archived = cli._archive_zero_trial_preflight_logs(
        checkpoint_path=checkpoint_path,
        failure_log=failure_log,
        preflight_log=preflight_log,
        resume=True,
    )

    assert len(archived) == 2
    assert not failure_log.exists()
    assert not preflight_log.exists()
    assert all(path.exists() for path in archived)
    assert any("call-failures" in path.name for path in archived)
    assert any("preflight-model-calls" in path.name for path in archived)


def test_wrapper_surfaces_terminal_failure_instead_of_throwing_generic_exit_code():
    text = Path("scripts/run-overnight-handoff.ps1").read_text(encoding="utf-8")
    assert "Get-Content -Path $TerminalLog -Tail" in text
    assert "ROOT FAILURE FROM TERMINAL LOG" in text
    assert "exit $WatcherExit" in text
    assert 'throw "Overnight handoff exited with code $WatcherExit' not in text
