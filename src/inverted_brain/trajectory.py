from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .contracts import AgentEvent

MUTATION_RE = re.compile(r"(^|\s)(rm|mv|cp|sed\s+-i|tee|truncate)(\s|$)|(^|[^>])>(?!>)")
VERIFY_RE = re.compile(r"\b(pytest|test|assert|diff|cmp|sha256sum|wc|grep)\b")
INSPECT_RE = re.compile(r"\b(cat|head|tail|sed\s+-n|find|ls|rg|grep)\b")
DEPENDENCY_RE = re.compile(r"dependency|requirements|schema|policy|manifest|config", re.I)


def _command_kind(command: str, seen_mutation: bool = False) -> str:
    if MUTATION_RE.search(command):
        return "mutation"
    if VERIFY_RE.search(command):
        return "verification"
    if INSPECT_RE.search(command):
        if seen_mutation:
            return "state_reread"
        if DEPENDENCY_RE.search(command):
            return "dependency_inspection"
        return "observation"
    return "tool_call"
def _event(index: int, kind: str, actor: str, raw: dict, source_id: str | None = None) -> AgentEvent:
    return AgentEvent(index=index, kind=kind, actor=actor, data=raw, timestamp=raw.get("timestamp") or raw.get("at"), source_id=source_id)


def normalize_qwen(raw_events: Iterable[dict]) -> list[AgentEvent]:
    out: list[AgentEvent] = []
    seen_mutation = False
    for raw in raw_events:
        kind = "observation"
        if raw.get("event") == "model_action":
            action = raw.get("action", {})
            if action.get("type") == "final":
                kind = "final"
            elif action.get("type") == "shell":
                kind = _command_kind(action.get("command", ""), seen_mutation)
                seen_mutation = seen_mutation or kind == "mutation"
        elif raw.get("event") == "tool_result":
            kind = "tool_result" if raw.get("exit_code") == 0 else "failure"
        elif raw.get("event") == "exception":
            kind = "failure"
        elif raw.get("event") == "final":
            kind = "final"
        out.append(_event(len(out), kind, "QWEN_BRAIN", raw, str(raw.get("step")) if raw.get("step") is not None else None))
    return out
def normalize_claude(raw_events: Iterable[dict]) -> list[AgentEvent]:
    out: list[AgentEvent] = []
    seen_mutation = False
    for raw in raw_events:
        kind = "observation"
        source_id = raw.get("uuid") or raw.get("request_id")
        if raw.get("type") == "assistant":
            for item in raw.get("message", {}).get("content", []):
                if item.get("type") == "tool_use" and item.get("name") == "mcp__arena__shell":
                    command = item.get("input", {}).get("command", "")
                    kind = _command_kind(command, seen_mutation)
                    seen_mutation = seen_mutation or kind == "mutation"
                    out.append(_event(len(out), kind, "CLAUDE_RAW", {**raw, "command": command}, source_id))
                elif item.get("type") == "text":
                    out.append(_event(len(out), "assertion", "CLAUDE_RAW", raw, source_id))
        elif raw.get("type") == "user" and raw.get("tool_use_result") is not None:
            out.append(_event(len(out), "tool_result", "CLAUDE_RAW", raw, source_id))
        elif raw.get("type") == "result":
            out.append(_event(len(out), "final" if not raw.get("is_error") else "failure", "CLAUDE_RAW", raw, source_id))
    return out


def normalize_codex(raw_events: Iterable[dict]) -> list[AgentEvent]:
    out: list[AgentEvent] = []
    seen_mutation = False
    for raw in raw_events:
        item = raw.get("item", {})
        source_id = item.get("id")
        if item.get("type") == "mcp_tool_call":
            command = item.get("arguments", {}).get("command", "")
            if raw.get("type") == "item.started":
                kind = _command_kind(command, seen_mutation)
                seen_mutation = seen_mutation or kind == "mutation"
            else:
                kind = "tool_result" if not item.get("error") else "failure"
            out.append(_event(len(out), kind, "CODEX_RAW", {**raw, "command": command}, source_id))
        elif item.get("type") == "agent_message":
            out.append(_event(len(out), "assertion", "CODEX_RAW", raw, source_id))
        elif raw.get("type") == "turn.completed":
            out.append(_event(len(out), "final", "CODEX_RAW", raw, source_id))
    return out


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
