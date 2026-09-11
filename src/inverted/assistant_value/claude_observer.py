from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CLAUDE_OBSERVER_EVENTS = (
    "SessionStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "SubagentStart",
    "SubagentStop",
    "Stop",
    "PreCompact",
    "PostCompact",
    "SessionEnd",
)


def write_observer_logger(path: str | Path) -> Path:
    """Write an out-of-band hook logger.

    The logger emits no stdout decision payload, never approves/blocks a tool,
    and does not inject context. It only appends hook stdin to a path supplied
    through TOMOGRAPHY_CLAUDE_HOOK_LOG.
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """from __future__ import annotations
import json
import os
import pathlib
import sys
import time

def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        payload = {
            "hook_parse_error": f"{type(exc).__name__}: {exc}",
            "raw": raw,
        }
    record = {
        "observer_monotonic_ns": time.monotonic_ns(),
        "payload": payload,
    }
    destination = os.environ.get("TOMOGRAPHY_CLAUDE_HOOK_LOG")
    if not destination:
        return 0
    path = pathlib.Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\\n") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False, default=str) + "\\n")
        handle.flush()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )
    return target


def claude_hook_settings(logger_path: str | Path) -> dict[str, Any]:
    """Create passive logging hooks for the documented lifecycle.

    These hooks intentionally return no decision and therefore must not alter
    tool inputs, permissions, outputs, or model context.
    """
    command = f'"{Path(logger_path).resolve()}"'
    # Use Python through the current interpreter only when the caller renders
    # the actual command. The placeholder keeps this pure/testable.
    hook = {"type": "command", "command": "{python} " + command}
    hooks: dict[str, list[dict[str, Any]]] = {}
    for event in CLAUDE_OBSERVER_EVENTS:
        if event in {"PreToolUse", "PostToolUse", "PostToolUseFailure"}:
            hooks[event] = [{"matcher": "*", "hooks": [dict(hook)]}]
        else:
            hooks[event] = [{"hooks": [dict(hook)]}]
    return {"hooks": hooks}


def install_claude_observer(
    workspace: str | Path,
    *,
    logger_path: str | Path,
    python_executable: str,
) -> Path:
    root = Path(workspace).resolve()
    settings_path = root / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = claude_hook_settings(logger_path)
    rendered = json.loads(json.dumps(settings))
    for entries in rendered["hooks"].values():
        for entry in entries:
            for hook in entry.get("hooks") or []:
                hook["command"] = str(hook["command"]).replace("{python}", f'"{python_executable}"')
    settings_path.write_text(
        json.dumps(rendered, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return settings_path
