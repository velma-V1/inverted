from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


MCP_SERVER_NAME = "tomography_probe"
MCP_TOOL_NAME = "lookup_release_rule"


def mcp_server_source() -> str:
    return r'''from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time

TOKEN = "mcp-current-2026"

def emit(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n")
    sys.stdout.flush()

def log(value):
    target = os.environ.get("TOMOGRAPHY_MCP_LOG")
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"ts_ns":time.time_ns(), **value}, sort_keys=True) + "\n")

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        msg = json.loads(raw)
    except Exception as exc:
        log({"kind":"parse_error","raw":raw,"error":f"{type(exc).__name__}: {exc}"})
        continue
    log({"kind":"request","message":msg})
    method = msg.get("method")
    request_id = msg.get("id")
    if method == "initialize" and request_id is not None:
        emit({
            "jsonrpc":"2.0",
            "id":request_id,
            "result":{
                "protocolVersion":"2025-06-18",
                "capabilities":{"tools":{"listChanged":False}},
                "serverInfo":{"name":"tomography-probe","version":"1.0.0"}
            }
        })
    elif method == "tools/list" and request_id is not None:
        emit({
            "jsonrpc":"2.0",
            "id":request_id,
            "result":{
                "tools":[{
                    "name":"lookup_release_rule",
                    "description":"Return the current deterministic compatibility token for the sealed tomography fixture.",
                    "inputSchema":{
                        "type":"object",
                        "properties":{"component":{"type":"string"}},
                        "required":["component"],
                        "additionalProperties":False
                    }
                }]
            }
        })
    elif method == "tools/call" and request_id is not None:
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if name != "lookup_release_rule":
            emit({
                "jsonrpc":"2.0",
                "id":request_id,
                "error":{"code":-32601,"message":"unknown tool"}
            })
        else:
            component = str(args.get("component") or "")
            result = {
                "component":component,
                "current_compatibility_token":TOKEN,
                "authority":"tomography-local-reference-service"
            }
            log({"kind":"tool_call","name":name,"arguments":args,"result":result})
            emit({
                "jsonrpc":"2.0",
                "id":request_id,
                "result":{
                    "content":[{
                        "type":"text",
                        "text":json.dumps(result, sort_keys=True)
                    }],
                    "isError":False
                }
            })
    elif request_id is not None:
        emit({
            "jsonrpc":"2.0",
            "id":request_id,
            "result":{}
        })
'''


def prepare_mcp_probe(
    *,
    workspace: str | Path,
    evidence_root: str | Path,
    subject: str,
    python_executable: str | None = None,
) -> dict[str, Any]:
    """Prepare a deterministic local stdio MCP treatment.

    The server lives outside the model workspace. Only the configuration that
    exposes the server is model-visible. No network, secrets, or user services
    are involved.
    """
    workspace_path = Path(workspace).resolve()
    evidence_path = Path(evidence_root).resolve()
    evidence_path.mkdir(parents=True, exist_ok=True)
    server = evidence_path / "tomography_mcp_server.py"
    log_path = evidence_path / "mcp-server-events.jsonl"
    server.write_text(mcp_server_source(), encoding="utf-8")
    python = str(python_executable or sys.executable)

    normalized = str(subject).strip().lower().replace("-", "_").replace(" ", "_")
    env = {"TOMOGRAPHY_MCP_LOG": str(log_path)}
    extra_args: list[str] = []
    config_path: Path | None = None

    if normalized in {"claude", "claude_code"}:
        config_path = evidence_path / "claude-mcp-config.json"
        config = {
            "mcpServers":{
                MCP_SERVER_NAME:{
                    "command":python,
                    "args":[str(server)],
                    "env":env,
                }
            }
        }
        config_path.write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        extra_args = ["--mcp-config", str(config_path)]
    elif normalized in {"codex", "codex_cli"}:
        # Current Codex accepts MCP stdio definitions through --config.
        # Use a CLI override instead of project config so trust-state loading is
        # not a second experimental factor.
        def q(value: str) -> str:
            return json.dumps(value)
        override = (
            f'mcp_servers.{MCP_SERVER_NAME}='
            + "{command="
            + q(python)
            + ",args=["
            + q(str(server))
            + "],env={TOMOGRAPHY_MCP_LOG="
            + q(str(log_path))
            + "}}"
        )
        extra_args = ["--config", override]
    else:
        raise ValueError(f"unsupported MCP probe subject: {subject}")

    return {
        "schema_version":1,
        "subject":normalized,
        "server_name":MCP_SERVER_NAME,
        "tool_name":MCP_TOOL_NAME,
        "server_path":str(server),
        "event_log_path":str(log_path),
        "config_path":str(config_path) if config_path else None,
        "extra_args":extra_args,
        "network_used":False,
        "credentials_used":False,
        "permission_bypass_added":False,
    }


def mcp_tool_was_called(event_log_path: str | Path) -> bool:
    path = Path(event_log_path)
    if not path.is_file():
        return False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if row.get("kind") == "tool_call" and row.get("name") == MCP_TOOL_NAME:
            return True
    return False


def mcp_server_readiness(event_log_path: str | Path) -> dict[str, Any]:
    path = Path(event_log_path)
    methods: list[str] = []
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if row.get("kind") != "request":
                continue
            message = row.get("message") or {}
            method = message.get("method")
            if isinstance(method, str):
                methods.append(method)
    initialized = "initialize" in methods
    tools_listed = "tools/list" in methods
    return {
        "initialized": initialized,
        "tools_listed": tools_listed,
        "ready": bool(initialized and tools_listed),
        "observed_methods": methods,
    }
