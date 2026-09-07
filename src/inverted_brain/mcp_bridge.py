from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SERVER_INFO = {"name": "inverted-brain-arena", "version": "0.1.0"}
TOOL = {
    "name": "shell",
    "description": "Run a POSIX shell command inside this arm's isolated Docker workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
        "additionalProperties": False,
    },
}


def _log(data: dict) -> None:
    target = os.environ.get("BRAIN_MCP_EVENT_LOG")
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **data}, sort_keys=True) + "\n")


def docker_exec(command: str) -> dict:
    name = os.environ.get("BRAIN_CONTAINER_NAME")
    if not name:
        raise RuntimeError("BRAIN_CONTAINER_NAME is required")
    completed = subprocess.run(
        ["docker", "exec", name, "sh", "-lc", command],
        capture_output=True, text=True, timeout=120,
    )
    result = {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    _log({"event": "shell", "command": command, **result})
    return result


def _ok(message_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_message(message: dict, exec_fn=docker_exec) -> dict | None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        protocol = (message.get("params") or {}).get("protocolVersion", "2025-06-18")
        return _ok(message_id, {"protocolVersion": protocol, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO})
    if method == "tools/list":
        return _ok(message_id, {"tools": [TOOL]})
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "shell":
            return _error(message_id, -32602, "unknown tool")
        command = (params.get("arguments") or {}).get("command")
        if not isinstance(command, str) or not command.strip():
            return _error(message_id, -32602, "command must be a non-empty string")
        try:
            result = exec_fn(command)
        except Exception as exc:
            return _error(message_id, -32000, f"shell failed: {type(exc).__name__}: {exc}")
        return _ok(message_id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "isError": False,
        })
    if message_id is None:
        return None
    return _error(message_id, -32601, f"method not found: {method}")


def serve() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            response = handle_message(json.loads(line))
        except Exception as exc:
            response = _error(None, -32700, f"parse/server error: {type(exc).__name__}: {exc}")
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve()
