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
    for event in events:
        hooks[str(event)] = [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": python,
                        "args": [str(logger), str(log)],
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
