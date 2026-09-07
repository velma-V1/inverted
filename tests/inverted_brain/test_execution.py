import json
import subprocess
from pathlib import Path

from inverted_brain.adapters import (
    QwenBrainAdapter, ClaudeRawAdapter, CodexRawAdapter,
    build_claude_command, build_codex_command, parse_qwen_action,
)
from inverted_brain.config import QWEN_MODEL, QWEN_OPTIONS
from inverted_brain.docker_workspace import DockerWorkspace


def test_qwen_action_contract_is_strict():
    assert parse_qwen_action('{"type":"shell","command":"cat a"}')["type"] == "shell"
    assert parse_qwen_action('{"type":"final","message":"done"}')["type"] == "final"


def test_frontier_commands_are_raw_and_restricted(tmp_path):
    mcp = tmp_path / "mcp.json"
    claude = build_claude_command(mcp, "TASK123")
    ctext = " ".join(claude)
    assert "TASK123" in ctext
    assert "Inverted" not in ctext
    assert "mcp__arena__shell" in ctext

    codex = build_codex_command(tmp_path / "neutral", "box", tmp_path / "events.jsonl")
    xtext = " ".join(codex)
    assert codex[-1] == "-"
    assert "--sandbox read-only" in xtext
    assert 'default_tools_approval_mode="approve"' in xtext


def test_qwen_adapter_records_exact_model_options(tmp_path):
    calls = []
    def fake_chat(messages, options):
        calls.append(options)
        return '{"type":"final","message":"done"}', {"eval_count": 1}

    runner = QwenBrainAdapter(chat_fn=fake_chat, box_factory=lambda *a, **k: NullBox())
    result = runner.run(
        tmp_path / "workspace",
        {"id": "t", "prompt": "do it"},
        tmp_path / "evidence",
        seed=4242,
    )
    assert result.status == "COMPLETE"
    assert calls[0]["model"] == QWEN_MODEL
    assert calls[0]["options"]["temperature"] == QWEN_OPTIONS["temperature"]
    assert calls[0]["options"]["seed"] == 4242


class NullBox:
    name = "null-box"
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def exec(self, command, timeout=60):
        return type("R", (), {"exit_code": 0, "stdout": "", "stderr": ""})()


def test_codex_prompt_is_delivered_via_stdin_once(tmp_path):
    seen = []
    def fake_process(command, **kwargs):
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="{}\n", stderr="")
    runner = CodexRawAdapter(process_fn=fake_process, box_factory=lambda *a, **k: NullBox())
    result = runner.run(
        tmp_path / "workspace",
        {"id": "t", "prompt": "LINE1\nLINE2"},
        tmp_path / "evidence",
    )
    assert result.status == "COMPLETE"
    assert len(seen) == 1
    assert "TASK:\nLINE1\nLINE2" in seen[0][1]["input"]


def test_docker_workspace_has_no_socket_or_sibling_access(tmp_path):
    a = tmp_path / "a"; b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    (a / "own.txt").write_text("own")
    (b / "secret.txt").write_text("secret")
    with DockerWorkspace(a, "TEST") as box:
        result = box.exec(["sh", "-lc", "test -f /workspace/own.txt && test ! -e /var/run/docker.sock && test ! -e /workspace/../b/secret.txt"])
        assert result.exit_code == 0
