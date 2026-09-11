from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shlex
from typing import Any, Iterable


@dataclass(frozen=True)
class SubjectCommand:
    subject: str
    argv: tuple[str, ...]
    cwd: str
    environment_overrides: dict[str, str] = field(default_factory=dict)
    output_mode: str = "jsonl"
    evidence_channel: str = "native"


def build_claude_code_command(
    *,
    prompt: str,
    cwd: str | Path,
    executable: str = "claude",
    extra_args: Iterable[str] = (),
) -> SubjectCommand:
    """Build a non-interactive Claude Code stream-json command.

    Extra arguments are explicit experiment configuration and are preserved in
    provenance. The harness does not silently add approval/permission bypasses.
    """
    argv = (
        str(executable),
        "-p",
        str(prompt),
        "--output-format",
        "stream-json",
        "--verbose",
        *tuple(str(x) for x in extra_args),
    )
    return SubjectCommand(
        subject="claude_code",
        argv=argv,
        cwd=str(Path(cwd)),
        output_mode="stream-json",
        evidence_channel="native",
    )


def build_codex_command(
    *,
    prompt: str,
    cwd: str | Path,
    executable: str = "codex",
    extra_args: Iterable[str] = (),
) -> SubjectCommand:
    """Build a non-interactive Codex JSON-event command."""
    argv = (
        str(executable),
        "exec",
        "--json",
        "-C",
        str(Path(cwd)),
        *tuple(str(x) for x in extra_args),
        str(prompt),
    )
    return SubjectCommand(
        subject="codex",
        argv=argv,
        cwd=str(Path(cwd)),
        output_mode="jsonl",
        evidence_channel="native",
    )


def command_for_subject(
    subject: str,
    *,
    prompt: str,
    cwd: str | Path,
    executable: str | None = None,
    extra_args: Iterable[str] = (),
) -> SubjectCommand:
    normalized = str(subject).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"claude", "claude_code"}:
        return build_claude_code_command(
            prompt=prompt,
            cwd=cwd,
            executable=executable or "claude",
            extra_args=extra_args,
        )
    if normalized in {"codex", "codex_cli"}:
        return build_codex_command(
            prompt=prompt,
            cwd=cwd,
            executable=executable or "codex",
            extra_args=extra_args,
        )
    raise ValueError(f"unsupported coding subject: {subject}")


def parse_jsonl_stream(text: str) -> dict[str, Any]:
    """Losslessly separate parseable JSON events from non-JSON text."""
    events: list[dict[str, Any]] = []
    non_json: list[dict[str, Any]] = []
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except Exception as exc:
            non_json.append(
                {
                    "line_number": line_number,
                    "text": raw,
                    "parse_error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if isinstance(value, dict):
            events.append(
                {
                    "line_number": line_number,
                    "event": value,
                }
            )
        else:
            non_json.append(
                {
                    "line_number": line_number,
                    "text": raw,
                    "parse_error": "JSON_VALUE_NOT_OBJECT",
                }
            )
    return {
        "events": events,
        "non_json": non_json,
        "line_count": len(str(text).splitlines()),
    }


def extract_subject_session_id(subject: str, parsed_events: Iterable[dict[str, Any]]) -> str | None:
    normalized = str(subject).strip().lower().replace("-", "_").replace(" ", "_")
    for wrapper in parsed_events:
        event = wrapper.get("event") if isinstance(wrapper, dict) else None
        if not isinstance(event, dict):
            continue
        if normalized in {"codex", "codex_cli"}:
            if event.get("type") == "thread.started" and event.get("thread_id"):
                return str(event["thread_id"])
            for key in ("thread_id", "session_id"):
                if event.get(key):
                    return str(event[key])
        else:
            for key in ("session_id", "sessionId", "conversation_id", "conversationId"):
                if event.get(key):
                    return str(event[key])
            payload = event.get("payload")
            if isinstance(payload, dict):
                for key in ("session_id", "sessionId"):
                    if payload.get(key):
                        return str(payload[key])
    return None


def sanitize_environment_snapshot(
    env: dict[str, str] | None = None,
    *,
    allow_names: Iterable[str] = (
        "PATH",
        "PATHEXT",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS",
        "SHELL",
        "COMSPEC",
        "TERM",
        "CI",
    ),
) -> dict[str, Any]:
    """Capture environment shape without secret values.

    Only explicitly allowlisted non-secret variables retain values. All other
    variables are represented by name only so the harness can detect environment
    differences without copying credentials into evidence.
    """
    source = dict(os.environ if env is None else env)
    allowed = set(str(x) for x in allow_names)
    return {
        "allowed_values": {key: source[key] for key in sorted(source) if key in allowed},
        "other_variable_names": [key for key in sorted(source) if key not in allowed],
        "variable_count": len(source),
    }


def subject_command_provenance(command: SubjectCommand) -> dict[str, Any]:
    return {
        "subject": command.subject,
        "argv": list(command.argv),
        "cwd": command.cwd,
        "environment_override_names": sorted(command.environment_overrides),
        "output_mode": command.output_mode,
        "evidence_channel": command.evidence_channel,
        "shell_rendering_for_humans_only": " ".join(shlex.quote(x) for x in command.argv),
    }


def expand_observable_subject_event(subject: str, raw_event: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand one native record into observable semantic events.

    This deliberately ignores non-exposed hidden reasoning. If a subject emits a
    safe reasoning *summary* field, that summary may be retained as an observable
    summary event. Raw source records remain preserved separately by the runner.
    """
    normalized = str(subject).strip().lower().replace("-", "_").replace(" ", "_")
    out: list[dict[str, Any]] = []

    if normalized in {"codex", "codex_cli"}:
        item = raw_event.get("item")
        if isinstance(item, dict):
            item_type = str(item.get("type") or "").lower()
            if item_type == "reasoning":
                summary = item.get("text") or item.get("summary")
                if summary:
                    out.append({"type":"reasoning_summary","summary":summary})
                return out or [raw_event]
            if item_type in {"command_execution","file_change","mcp_tool_call","web_search","todo_list","agent_message"}:
                out.append(raw_event)
                return out
            if item_type in {"collab_tool_call","collab_agent_tool_call"}:
                tool = str(item.get("tool") or item.get("name") or "").lower()
                if "spawn" in tool:
                    out.append({"type":"collab_spawn","item":item})
                else:
                    out.append(raw_event)
                return out
        return [raw_event]

    if normalized in {"claude", "claude_code"}:
        event_type = str(raw_event.get("type") or "").lower()
        if event_type in {"system","init"}:
            return [{"type":"session_started","source_event":raw_event}]
        if event_type in {"result","final"}:
            return [{"type":"agent_message","source_event":raw_event},{"type":"stop","source_event":raw_event}]
        if event_type == "assistant":
            message = raw_event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                tool_map = {
                    "bash":"command_execution",
                    "read":"file_read",
                    "write":"write",
                    "edit":"edit",
                    "multiedit":"edit",
                    "grep":"search",
                    "glob":"search",
                    "websearch":"web",
                    "webfetch":"web",
                    "task":"subagent_start",
                    "agent":"subagent_start",
                }
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = str(block.get("type") or "").lower()
                    if block_type == "tool_use":
                        name = str(block.get("name") or "")
                        mapped = tool_map.get(name.lower(), "unknown")
                        out.append({
                            "type":mapped,
                            "tool_name":name,
                            "tool_use_id":block.get("id"),
                            "input":block.get("input"),
                        })
                    elif block_type in {"reasoning_summary","summary"}:
                        out.append({
                            "type":"reasoning_summary",
                            "summary":block.get("text") or block.get("summary"),
                        })
            return out or [raw_event]
        return [raw_event]

    return [raw_event]


def expand_observable_subject_stream(subject: str, raw_events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for event in raw_events:
        expanded.extend(expand_observable_subject_event(subject, event))
    return expanded
