from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from inverted.assistant_value.coding_tomography_observers import (
    CLAUDE_OBSERVER_EVENTS,
    load_rollout_jsonl,
    prepare_claude_hook_observer,
    resolve_rollout_path,
)


def test_claude_observer_installs_logging_only_hooks(tmp_path: Path):
    workspace = tmp_path / "workspace"
    evidence = tmp_path / "evidence"
    workspace.mkdir()

    record = prepare_claude_hook_observer(
        workspace=workspace,
        evidence_root=evidence,
    )

    settings = json.loads(
        (workspace / ".claude" / "settings.local.json").read_text(encoding="utf-8")
    )
    assert record["decision_output"] is False
    assert record["native_performance_eligible"] is False
    assert set(settings["hooks"]) == set(CLAUDE_OBSERVER_EVENTS)

    for event, groups in settings["hooks"].items():
        assert len(groups) == 1
        handler = groups[0]["hooks"][0]
        assert handler["type"] == "command"
        assert handler["command"] == sys.executable
        assert handler["args"][1] == record["event_log_path"]
        assert "permissionDecision" not in json.dumps(handler)


def test_claude_hook_logger_preserves_event_and_emits_no_stdout_decision(tmp_path: Path):
    workspace = tmp_path / "workspace"
    evidence = tmp_path / "evidence"
    workspace.mkdir()
    record = prepare_claude_hook_observer(
        workspace=workspace,
        evidence_root=evidence,
    )

    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest -q"},
    }
    completed = subprocess.run(
        [sys.executable, record["logger_path"], record["event_log_path"]],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout == ""
    rows = [
        json.loads(line)
        for line in Path(record["event_log_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["hook_event_name"] == "PreToolUse"
    assert rows[0]["tool_name"] == "Bash"
    assert rows[0]["tool_input"]["command"] == "pytest -q"


def test_codex_rollout_resolution_uses_exact_session_template_only(tmp_path: Path):
    session_id = "thread-abc"
    exact = tmp_path / f"rollout-{session_id}.jsonl"
    decoy = tmp_path / "rollout-other.jsonl"
    exact.write_text('{"type":"item.completed"}\n', encoding="utf-8")
    decoy.write_text('{"type":"secret-decoy"}\n', encoding="utf-8")

    resolved = resolve_rollout_path(
        str(tmp_path / "rollout-{session_id}.jsonl"),
        session_id=session_id,
    )

    assert resolved == exact.resolve()
    assert resolve_rollout_path(str(tmp_path / "missing-{session_id}.jsonl"), session_id=session_id) is None


def test_rollout_loader_preserves_unparseable_rows(tmp_path: Path):
    path = tmp_path / "rollout.jsonl"
    path.write_text(
        '{"type":"thread.started","thread_id":"abc"}\nnot-json\n',
        encoding="utf-8",
    )

    rows = load_rollout_jsonl(path)

    assert rows[0]["type"] == "thread.started"
    assert rows[1]["type"] == "rollout_unparsed"
    assert rows[1]["raw_text"] == "not-json"
