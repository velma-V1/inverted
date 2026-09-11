from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from inverted.assistant_value.coding_tomography_mcp import (
    MCP_SERVER_NAME,
    MCP_TOOL_NAME,
    mcp_server_readiness,
    mcp_tool_was_called,
    prepare_mcp_probe,
)


def _rpc(proc: subprocess.Popen[str], message: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line, message
    return json.loads(line)


def test_mcp_probe_server_is_deterministic_local_and_auditable(tmp_path: Path):
    workspace = tmp_path / "workspace"
    evidence = tmp_path / "evidence"
    workspace.mkdir()

    probe = prepare_mcp_probe(
        workspace=workspace,
        evidence_root=evidence,
        subject="claude_code",
        python_executable=sys.executable,
    )

    assert probe["server_name"] == MCP_SERVER_NAME
    assert probe["tool_name"] == MCP_TOOL_NAME
    assert probe["network_used"] is False
    assert probe["credentials_used"] is False
    assert probe["permission_bypass_added"] is False
    assert Path(probe["server_path"]).is_file()
    assert Path(probe["server_path"]).parent == evidence.resolve()
    assert workspace.resolve() not in Path(probe["server_path"]).parents

    env = __import__("os").environ.copy()
    env["TOMOGRAPHY_MCP_LOG"] = probe["event_log_path"]
    proc = subprocess.Popen(
        [sys.executable, probe["server_path"]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        initialized = _rpc(
            proc,
            {
                "jsonrpc":"2.0",
                "id":1,
                "method":"initialize",
                "params":{
                    "protocolVersion":"2025-06-18",
                    "capabilities":{},
                    "clientInfo":{"name":"test","version":"1"},
                },
            },
        )
        assert initialized["result"]["serverInfo"]["name"] == "tomography-probe"

        tools = _rpc(
            proc,
            {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}},
        )
        names = {row["name"] for row in tools["result"]["tools"]}
        assert names == {MCP_TOOL_NAME}

        called = _rpc(
            proc,
            {
                "jsonrpc":"2.0",
                "id":3,
                "method":"tools/call",
                "params":{
                    "name":MCP_TOOL_NAME,
                    "arguments":{"component":"engine"},
                },
            },
        )
        payload = json.loads(called["result"]["content"][0]["text"])
        assert payload == {
            "authority":"tomography-local-reference-service",
            "component":"engine",
            "current_compatibility_token":"mcp-current-2026",
        }
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)

    readiness = mcp_server_readiness(probe["event_log_path"])
    assert readiness["ready"] is True
    assert "initialize" in readiness["observed_methods"]
    assert "tools/list" in readiness["observed_methods"]
    assert mcp_tool_was_called(probe["event_log_path"]) is True


def test_mcp_subject_configuration_is_subject_specific_and_no_bypass(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    claude = prepare_mcp_probe(
        workspace=workspace,
        evidence_root=tmp_path / "claude-evidence",
        subject="claude_code",
        python_executable=sys.executable,
    )
    codex = prepare_mcp_probe(
        workspace=workspace,
        evidence_root=tmp_path / "codex-evidence",
        subject="codex",
        python_executable=sys.executable,
    )

    assert claude["extra_args"][0] == "--mcp-config"
    config = json.loads(Path(claude["config_path"]).read_text(encoding="utf-8"))
    assert MCP_SERVER_NAME in config["mcpServers"]

    assert codex["extra_args"][0] == "--config"
    assert f"mcp_servers.{MCP_SERVER_NAME}" in codex["extra_args"][1]

    serialized = json.dumps({"claude":claude,"codex":codex}).lower()
    assert "dangerously" not in serialized
    assert "bypass" not in serialized
    assert "api_key" not in serialized
