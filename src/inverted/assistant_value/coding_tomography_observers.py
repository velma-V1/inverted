from __future__ import annotations

import json
from pathlib import Path
import shlex
import sys
from typing import Any, Iterable


CLAUDE_OBSERVER_EVENTS = (
    "SessionStart",
    "InstructionsLoaded",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PermissionDenied",
    "PostToolUse",
    "PostToolUseFailure",
    "PostToolBatch",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "Stop",
    "StopFailure",
    "PreCompact",
    "PostCompact",
    "PreModelSwitch",
    "PostModelSwitch",
    "CwdChanged",
    "FileChanged",
    "SessionEnd",
)


def _hook_logger_source() -> str:
    return """from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time

def main():
    if len(sys.argv) != 2:
        return 2
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception as exc:
        payload = {
            "hook_event_name": "UNPARSED_HOOK_INPUT",
            "raw_text": raw,
            "parse_error": f"{type(exc).__name__}: {exc}",
        }
    payload = {
        "observer_timestamp_ns": time.time_ns(),
        "observer_pid": os.getpid(),
        **payload,
    }
    with target.open("a", encoding="utf-8", newline="\\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str) + "\\n")
        handle.flush()
        os.fsync(handle.fileno())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def prepare_claude_hook_observer(
    *,
    workspace: str | Path,
    evidence_root: str | Path,
    python_executable: str | None = None,
    events: Iterable[str] = CLAUDE_OBSERVER_EVENTS,
) -> dict[str, Any]:
    """Install logging-only project-local hooks for an observability arm.

    The hook prints no decision and exits 0, so normal Claude Code permission
    flow remains authoritative. This arm is intentionally excluded from native
    performance comparisons because hook process startup adds timing overhead.
    """
    workspace_path = Path(workspace).resolve()
    evidence_path = Path(evidence_root).resolve()
    evidence_path.mkdir(parents=True, exist_ok=True)

    logger = evidence_path / "claude-hook-logger.py"
    log = evidence_path / "claude-hook-events.jsonl"
    logger.write_text(_hook_logger_source(), encoding="utf-8")

    python = str(python_executable or sys.executable)
    hooks: dict[str, Any] = {}
    command = f'"{python}" "{logger}" "{log}"'
    for event in events:
        hooks[str(event)] = [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ]
            }
        ]

    settings_dir = workspace_path / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings = settings_dir / "settings.local.json"
    settings.write_text(
        json.dumps({"hooks": hooks}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "subject": "claude_code",
        "mode": "LOGGING_ONLY_HOOKS",
        "settings_path": str(settings),
        "logger_path": str(logger),
        "event_log_path": str(log),
        "events": list(events),
        "decision_output": False,
        "native_performance_eligible": False,
    }


def resolve_rollout_path(
    template: str | None,
    *,
    session_id: str | None,
) -> Path | None:
    """Resolve one exact user-supplied rollout template; never scan a home tree."""
    if not template or not session_id:
        return None
    rendered = str(template).replace("{session_id}", str(session_id))
    path = Path(rendered).expanduser().resolve()
    return path if path.is_file() else None


def load_rollout_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = Path(path)
    for line_number, raw in enumerate(
        source.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except Exception as exc:
            rows.append(
                {
                    "type": "rollout_unparsed",
                    "line_number": line_number,
                    "raw_text": raw,
                    "parse_error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            rows.append(
                {
                    "type": "rollout_non_object",
                    "line_number": line_number,
                    "value": value,
                }
            )
    return rows


def observer_provenance(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(record, sort_keys=True, default=str))


def locate_codex_rollout_by_thread_id(
    thread_id: str,
    *,
    codex_home: str | Path | None = None,
) -> dict[str, Any]:
    """Search only CODEX_HOME/sessions for a filename containing exact thread ID."""
    import os
    tid = str(thread_id).strip()
    if not tid:
        return {"status":"NO_THREAD_ID","path":None,"candidates":[]}
    root = (
        Path(codex_home).expanduser().resolve()
        if codex_home is not None
        else Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser().resolve()
    )
    sessions = root / "sessions"
    if not sessions.is_dir():
        return {"status":"SESSIONS_DIR_MISSING","path":None,"sessions_root":str(sessions),"candidates":[]}
    matches = [
        path for path in sessions.rglob("*")
        if path.is_file() and tid in path.name
    ]
    matches.sort(key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
    return {
        "status":"FOUND" if matches else "NOT_FOUND_BY_EXACT_THREAD_ID",
        "path":str(matches[0]) if matches else None,
        "sessions_root":str(sessions),
        "candidates":[str(path) for path in matches],
        "selection_rule":"filename contains exact emitted thread_id; no home-wide content scan",
    }


def codex_rollout_observable_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project exact-thread rollout records into safe observable trajectory events."""
    out: list[dict[str, Any]] = []
    for row in rows:
        row_type = str(row.get("type") or "")
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        ptype = str(payload.get("type") or "")

        if row_type == "event_msg":
            if ptype == "agent_reasoning":
                text = payload.get("text")
                if isinstance(text, str) and text:
                    out.append({"type":"reasoning_summary","summary":text,"rollout_type":ptype})
            elif ptype == "task_started":
                out.append({"type":"session_started","rollout_type":ptype})
            elif ptype == "task_complete":
                out.append({"type":"stop","rollout_type":ptype})
            elif ptype in {"agent_message","plan_update","turn_aborted"}:
                out.append({"type":ptype,"payload":payload})
            continue

        if row_type == "response_item":
            if ptype == "reasoning":
                summaries = payload.get("summary")
                if isinstance(summaries, list):
                    for item in summaries:
                        if isinstance(item, dict) and isinstance(item.get("text"), str):
                            out.append({"type":"reasoning_summary","summary":item["text"],"rollout_type":ptype})
                continue
            if ptype in {"function_call","custom_tool_call","local_shell_call","mcp_tool_call"}:
                name = payload.get("name") or payload.get("tool_name") or ptype
                lowered = str(name).lower()
                mapped = (
                    "collab_spawn"
                    if "spawn" in lowered or "collab" in lowered
                    else "mcp"
                    if "mcp" in lowered
                    else "command_execution"
                )
                out.append({"type":mapped,"tool_name":name,"payload":payload})
                continue
            if ptype in {"message","agent_message"}:
                out.append({"type":"agent_message","payload":payload})
                continue

        if row_type in {"turn_context","session_meta"}:
            out.append({"type":"context_load","rollout_type":row_type})
    return out
