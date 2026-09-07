from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import QWEN_MODEL, QWEN_OPTIONS
from .contracts import TrialResult
from .docker_workspace import DockerWorkspace
from .evidence import append_jsonl, write_json

ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = Path(__file__).with_name("mcp_bridge.py")
CORE_PATH = ROOT / "configs" / "inverted_brain" / "brain_core_v1_frozen.txt"
PYTHON_EXE = Path(sys.executable).resolve()
OLLAMA_API = "http://127.0.0.1:11434/api/chat"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def arena_prompt(task_prompt: str) -> str:
    return (
        "CONTROLLED TERMINAL ARENA. The task workspace exists only behind the MCP server named arena. "
        "Use arena shell for every workspace inspection, command, and edit. Do not inspect host files, auth, or config. "
        "Complete the visible task and verify the resulting workspace.\n\nTASK:\n" + task_prompt
    )


def make_mcp_config(container_name: str, event_log: Path) -> dict:
    return {
        "mcpServers": {
            "arena": {
                "type": "stdio",
                "command": str(PYTHON_EXE),
                "args": [str(MCP_SERVER)],
                "env": {
                    "BRAIN_CONTAINER_NAME": container_name,
                    "BRAIN_MCP_EVENT_LOG": str(Path(event_log).resolve()),
                },
            }
        }
    }


def build_claude_command(mcp_config_path: Path, prompt: str) -> list[str]:
    return [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--include-hook-events", "--no-session-persistence",
        "--strict-mcp-config", "--mcp-config", str(Path(mcp_config_path).resolve()),
        "--restricted", "--tools", "",
        "--allowedTools", "mcp__arena__shell",
        "--permission-mode", "dontAsk", "--permission-prompts", "none",
        "--disable-slash-commands", "--no-chrome",
    ]


def _toml(value: str) -> str:
    return json.dumps(value)


def build_codex_command(neutral_cwd: Path, container_name: str, event_log: Path) -> list[str]:
    neutral_cwd = Path(neutral_cwd).resolve()
    neutral_cwd.mkdir(parents=True, exist_ok=True)
    return [
        "codex", "exec", "--json", "--ephemeral",
        "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
        "--sandbox", "read-only",
        "-c", 'approval_policy="never"',
        "--cd", str(neutral_cwd),
        "-c", f"mcp_servers.arena.command={_toml(str(PYTHON_EXE))}",
        "-c", 'mcp_servers.arena.default_tools_approval_mode="approve"',
        "-c", f"mcp_servers.arena.args={json.dumps([str(MCP_SERVER)])}",
        "-c", f"mcp_servers.arena.env.BRAIN_CONTAINER_NAME={_toml(container_name)}",
        "-c", f"mcp_servers.arena.env.BRAIN_MCP_EVENT_LOG={_toml(str(Path(event_log).resolve()))}",
        "-",
    ]


def parse_qwen_action(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    obj = json.loads(cleaned)
    if obj.get("type") == "shell" and isinstance(obj.get("command"), str):
        return {"type": "shell", "command": obj["command"]}
    if obj.get("type") == "final" and isinstance(obj.get("message", ""), str):
        return {"type": "final", "message": obj.get("message", "")}
    raise ValueError("invalid Qwen arena action")


def build_qwen_system_prompt(candidate_addendum: str | None = None) -> str:
    core = CORE_PATH.read_text(encoding="utf-8")
    contract = """

INVERTED BRAIN TERMINAL CONTRACT
Operate only in the disposable workspace. Return exactly one JSON object per turn.
Use {"type":"shell","command":"<POSIX command>"} for workspace actions.
Use {"type":"final","message":"<brief result>"} only after observable verification.
Do not invent tool results. Preserve explicit constraints and negative evidence.
"""
    if candidate_addendum:
        contract += "\nCANDIDATE MECHANISM UNDER TEST (single addendum only):\n" + candidate_addendum.strip() + "\n"
    return core + contract


def ollama_chat(messages: list[dict], request: dict) -> tuple[str, dict]:
    payload = {
        "model": request["model"],
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "format": "json",
        "options": request["options"],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        raw = response.read().decode("utf-8")
    obj = json.loads(raw)
    return obj.get("message", {}).get("content", ""), obj


class QwenBrainAdapter:
    arm = "QWEN_BRAIN"

    def __init__(self, chat_fn: Callable | None = None, box_factory: Callable | None = None, max_steps: int = 10, candidate_addendum: str | None = None):
        self.chat_fn = chat_fn or ollama_chat
        self.box_factory = box_factory or DockerWorkspace
        self.max_steps = max_steps
        self.candidate_addendum = candidate_addendum

    def run(self, workspace: Path, task: dict, evidence_dir: Path, seed: int) -> TrialResult:
        workspace = Path(workspace).resolve()
        evidence_dir = Path(evidence_dir).resolve()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        events_path = evidence_dir / "events.jsonl"
        calls_path = evidence_dir / "model_calls.jsonl"
        started = time.perf_counter()
        messages = [
            {"role": "system", "content": build_qwen_system_prompt(self.candidate_addendum)},
            {"role": "user", "content": task["prompt"]},
        ]
        status = "FAILED"
        metadata = {"model": QWEN_MODEL, "seed": seed, "steps": 0}
        append_jsonl(events_path, {"event": "start", "task_id": task["id"], "arm": self.arm, "at": now_iso()})
        try:
            with self.box_factory(workspace, self.arm) as box:
                for step in range(1, self.max_steps + 1):
                    metadata["steps"] = step
                    options = dict(QWEN_OPTIONS); options["seed"] = seed
                    request = {"model": QWEN_MODEL, "options": options, "step": step}
                    text, raw = self.chat_fn(messages, request)
                    append_jsonl(calls_path, {"request": {**request, "messages": messages}, "response": raw, "text": text})
                    action = parse_qwen_action(text)
                    append_jsonl(events_path, {"event": "model_action", "step": step, "action": action})
                    messages.append({"role": "assistant", "content": text})
                    if action["type"] == "final":
                        append_jsonl(events_path, {"event": "final", "step": step, "message": action["message"]})
                        status = "COMPLETE"
                        break
                    result = box.exec(["sh", "-lc", action["command"]], timeout=120)
                    append_jsonl(events_path, {
                        "event": "tool_result", "step": step, "command": action["command"],
                        "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr,
                    })
                    messages.append({"role": "user", "content": "TOOL_RESULT " + json.dumps({
                        "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr,
                    }, ensure_ascii=False)})
        except Exception as exc:
            status = "ABORTED_INFRASTRUCTURE" if isinstance(exc, (subprocess.SubprocessError, OSError)) else "FAILED"
            append_jsonl(events_path, {"event": "exception", "type": type(exc).__name__, "message": str(exc)})
        wall = time.perf_counter() - started
        append_jsonl(events_path, {"event": "end", "status": status, "wall_seconds": wall, "at": now_iso()})
        write_json(evidence_dir / "result.json", {"arm": self.arm, "status": status, "wall_seconds": wall, "metadata": metadata})
        return TrialResult(
            trial_id=task["id"], arm=self.arm, status=status,
            outcome_passed=False, process_passed=True, workspace=str(workspace),
            wall_seconds=wall, metadata={**metadata, "evidence_dir": str(evidence_dir)},
        )


class _BaseFrontierAdapter:
    arm = "BASE"

    def __init__(self, process_fn: Callable | None = None, box_factory: Callable | None = None):
        self.process_fn = process_fn or subprocess.run
        self.box_factory = box_factory or DockerWorkspace

    def build_command(self, neutral: Path, box_name: str, event_log: Path, prompt: str, mcp_path: Path) -> list[str]:
        raise NotImplementedError

    def process_kwargs(self, prompt: str) -> dict:
        return {"stdin": subprocess.DEVNULL}

    def run(self, workspace: Path, task: dict, evidence_dir: Path, seed: int | None = None) -> TrialResult:
        workspace = Path(workspace).resolve()
        evidence_dir = Path(evidence_dir).resolve()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        neutral = evidence_dir / "_neutral"; neutral.mkdir(exist_ok=True)
        event_log = evidence_dir / "mcp_events.jsonl"
        mcp_path = evidence_dir / "mcp_config.json"
        stdout_path = evidence_dir / "stdout.jsonl"
        stderr_path = evidence_dir / "stderr.txt"
        prompt = arena_prompt(task["prompt"])
        started = time.perf_counter()
        status = "FAILED"
        command: list[str] = []
        exit_code = 2
        try:
            with self.box_factory(workspace, self.arm) as box:
                write_json(mcp_path, make_mcp_config(box.name, event_log))
                command = self.build_command(neutral, box.name, event_log, prompt, mcp_path)
                write_json(evidence_dir / "request.json", {"arm": self.arm, "task_id": task["id"], "prompt": prompt, "command": command})
                resolved = list(command)
                found = shutil.which(resolved[0])
                if found:
                    resolved[0] = found
                completed = self.process_fn(
                    resolved, cwd=str(neutral), capture_output=True, text=True, timeout=900,
                    **self.process_kwargs(prompt),
                )
                exit_code = int(completed.returncode)
                stdout_path.write_text(completed.stdout or "", encoding="utf-8")
                stderr_path.write_text(completed.stderr or "", encoding="utf-8")
                status = "COMPLETE" if exit_code == 0 else "FAILED"
        except subprocess.TimeoutExpired as exc:
            status = "TIMEOUT"
            stderr_path.write_text(str(exc), encoding="utf-8")
        except Exception as exc:
            status = "ABORTED_INFRASTRUCTURE"
            stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        wall = time.perf_counter() - started
        write_json(evidence_dir / "result.json", {
            "arm": self.arm, "status": status, "exit_code": exit_code,
            "wall_seconds": wall, "command": command,
        })
        return TrialResult(
            trial_id=task["id"], arm=self.arm, status=status,
            outcome_passed=False, process_passed=True,
            workspace=str(workspace), wall_seconds=wall,
            metadata={"exit_code": exit_code, "evidence_dir": str(evidence_dir)},
        )


class ClaudeRawAdapter(_BaseFrontierAdapter):
    arm = "CLAUDE_RAW"

    def build_command(self, neutral: Path, box_name: str, event_log: Path, prompt: str, mcp_path: Path) -> list[str]:
        return build_claude_command(mcp_path, prompt)


class CodexRawAdapter(_BaseFrontierAdapter):
    arm = "CODEX_RAW"

    def process_kwargs(self, prompt: str) -> dict:
        return {"input": prompt}

    def build_command(self, neutral: Path, box_name: str, event_log: Path, prompt: str, mcp_path: Path) -> list[str]:
        return build_codex_command(neutral, box_name, event_log)


def _intervention_instruction(intervention) -> str:
    kind = intervention.kind
    target = intervention.target_kind
    replacement = intervention.replacement or ""
    if kind == "remove":
        return f"EXPERIMENTAL BEHAVIOR CONSTRAINT: do not perform behavior `{target}`. Solve the task otherwise normally."
    if kind == "force":
        return f"EXPERIMENTAL BEHAVIOR CONSTRAINT: before finalizing, explicitly perform behavior `{target}` using observable tools."
    if kind == "replace":
        return f"EXPERIMENTAL BEHAVIOR CONSTRAINT: where you would perform `{target}`, perform `{replacement}` instead."
    if kind == "delay":
        return f"EXPERIMENTAL BEHAVIOR CONSTRAINT: delay `{target}` until after `{replacement}` if both are applicable."
    return f"EXPERIMENTAL BEHAVIOR CONSTRAINT: use the paired behavior `{target}` plus `{replacement}` when applicable."


def _score_intervention_result(result: TrialResult, task: dict) -> TrialResult:
    from .trajectory import normalize_qwen, normalize_claude, normalize_codex, read_jsonl
    from .verifier import verify_outcome, evaluate_process
    evidence = Path(result.metadata.get("evidence_dir", ""))
    events = []
    try:
        if result.arm.startswith("QWEN"):
            events = normalize_qwen(read_jsonl(evidence / "events.jsonl"))
        elif result.arm.startswith("CLAUDE"):
            events = normalize_claude(read_jsonl(evidence / "stdout.jsonl"))
        elif result.arm.startswith("CODEX"):
            events = normalize_codex(read_jsonl(evidence / "stdout.jsonl"))
    except Exception:
        events = []
    outcome = verify_outcome(task, Path(result.workspace)) if result.status == "COMPLETE" else None
    process = evaluate_process(task, events, result.status)
    result.events = events
    result.outcome_passed = bool(outcome and outcome.passed)
    result.process_passed = process.passed
    return result


def _qwen_normalize(self, evidence_dir: Path):
    from .trajectory import normalize_qwen, read_jsonl
    return normalize_qwen(read_jsonl(Path(evidence_dir) / "events.jsonl"))


def _frontier_normalize(self, evidence_dir: Path):
    from .trajectory import normalize_claude, normalize_codex, read_jsonl
    raw = read_jsonl(Path(evidence_dir) / "stdout.jsonl")
    return normalize_claude(raw) if self.arm.startswith("CLAUDE") else normalize_codex(raw)


def _qwen_run_intervention(self, workspace, task, intervention, seed):
    adapter = QwenBrainAdapter(
        chat_fn=self.chat_fn, box_factory=self.box_factory,
        max_steps=self.max_steps,
        candidate_addendum=_intervention_instruction(intervention),
    )
    result = adapter.run(Path(workspace), task, Path(workspace).parent / "intervention_evidence", seed=seed)
    return _score_intervention_result(result, task)


def _frontier_run_intervention(self, workspace, task, intervention, seed):
    modified = dict(task)
    modified["prompt"] = task["prompt"] + "\n\n" + _intervention_instruction(intervention)
    result = self.run(Path(workspace), modified, Path(workspace).parent / "intervention_evidence", seed=seed)
    return _score_intervention_result(result, task)


QwenBrainAdapter.normalize_evidence = _qwen_normalize
QwenBrainAdapter.run_intervention = _qwen_run_intervention
ClaudeRawAdapter.normalize_evidence = _frontier_normalize
CodexRawAdapter.normalize_evidence = _frontier_normalize
ClaudeRawAdapter.run_intervention = _frontier_run_intervention
CodexRawAdapter.run_intervention = _frontier_run_intervention
