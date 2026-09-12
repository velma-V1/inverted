from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any


def codex_home(env: dict[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    configured = source.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def locate_rollout_by_thread_id(
    thread_id: str,
    *,
    home: str | Path | None = None,
) -> dict[str, Any]:
    """Locate only the exact user-owned Codex session artifact for this run.

    This intentionally does not grep the whole home directory. It searches
    CODEX_HOME/sessions for filenames containing the exact emitted thread ID.
    """
    tid = str(thread_id).strip()
    if not tid:
        return {"status":"NO_THREAD_ID","path":None,"candidates":[]}
    root = Path(home).resolve() if home is not None else codex_home()
    sessions = root / "sessions"
    if not sessions.is_dir():
        return {"status":"SESSIONS_DIR_MISSING","path":None,"sessions_root":str(sessions),"candidates":[]}

    matches = [
        path for path in sessions.rglob("*")
        if path.is_file() and tid in path.name
    ]
    matches.sort(key=lambda path: (path.stat().st_mtime_ns, str(path)), reverse=True)
    if not matches:
        return {
            "status":"NOT_FOUND_BY_EXACT_THREAD_ID",
            "path":None,
            "sessions_root":str(sessions),
            "candidates":[],
        }
    return {
        "status":"FOUND",
        "path":str(matches[0]),
        "sessions_root":str(sessions),
        "candidates":[str(path) for path in matches],
    }


def copy_rollout_evidence(
    thread_id: str,
    destination: str | Path,
    *,
    home: str | Path | None = None,
) -> dict[str, Any]:
    located = locate_rollout_by_thread_id(thread_id, home=home)
    if located.get("status") != "FOUND":
        return located
    source = Path(str(located["path"]))
    dest = Path(destination).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return {
        **located,
        "copied_to":str(dest),
        "bytes":dest.stat().st_size,
    }


def parse_rollout_jsonl(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {"rows":[],"parse_errors":[{"error":"MISSING_FILE","path":str(source)}]}
    rows = []
    errors = []
    for line_number, raw in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except Exception as exc:
            errors.append({
                "line_number":line_number,
                "error":f"{type(exc).__name__}: {exc}",
            })
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            errors.append({
                "line_number":line_number,
                "error":"JSON_VALUE_NOT_OBJECT",
            })
    return {"rows":rows,"parse_errors":errors}


def rollout_observable_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project user-owned rollout records into observable event records.

    Raw rollout rows remain the authority. This projection keeps only event
    types/summary/tool metadata useful to trajectory normalization; it does not
    expose or label private hidden chain-of-thought.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        row_type = str(row.get("type") or "")
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        ptype = str(payload.get("type") or "")

        if row_type == "event_msg":
            if ptype == "agent_reasoning":
                # Treat any product-exposed agent reasoning text as a reasoning
                # summary channel, not as proof of private internal thought.
                text = payload.get("text")
                if text:
                    out.append({"type":"reasoning_summary","summary":text,"rollout_type":ptype})
            elif ptype in {"task_started","task_complete"}:
                out.append({"type":"session_started" if ptype=="task_started" else "stop","rollout_type":ptype})
            elif ptype in {"agent_message","plan_update","turn_aborted"}:
                out.append({"type":ptype,"payload":payload})
            continue

        if row_type == "response_item":
            if ptype == "reasoning":
                summaries = payload.get("summary")
                if isinstance(summaries, list):
                    for item in summaries:
                        if isinstance(item, dict) and item.get("text"):
                            out.append({"type":"reasoning_summary","summary":item.get("text"),"rollout_type":ptype})
                continue
            if ptype in {"function_call","custom_tool_call","local_shell_call","mcp_tool_call"}:
                name = payload.get("name") or payload.get("tool_name") or ptype
                lowered = str(name).lower()
                mapped = (
                    "subagent_start" if "spawn" in lowered or "collab" in lowered
                    else "mcp" if "mcp" in lowered
                    else "command"
                )
                out.append({"type":mapped,"tool_name":name,"payload":payload})
                continue
            if ptype in {"message","agent_message"}:
                out.append({"type":"agent_message","payload":payload})
                continue

        if row_type in {"turn_context","session_meta"}:
            out.append({"type":"context_load","rollout_type":row_type})

    return out
