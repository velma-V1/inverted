from __future__ import annotations

from inverted.assistant_value.coding_subjects import (
    build_claude_code_command,
    build_codex_command,
    expand_observable_subject_stream,
    extract_observable_final_text,
    parse_jsonl_stream,
    sanitize_environment_snapshot,
)


def test_claude_native_command_has_stream_json_without_permission_bypass(tmp_path):
    cmd = build_claude_code_command(prompt="fix it", cwd=tmp_path)
    argv = list(cmd.argv)

    assert argv[:2] == ["claude", "-p"]
    assert "--output-format" in argv
    assert "stream-json" in argv
    assert "--verbose" in argv
    joined = " ".join(argv).lower()
    assert "dangerously" not in joined
    assert "bypass" not in joined
    assert "skip-permissions" not in joined


def test_codex_native_command_has_json_event_mode_without_approval_bypass(tmp_path):
    cmd = build_codex_command(prompt="fix it", cwd=tmp_path)
    argv = list(cmd.argv)

    assert argv[:3] == ["codex", "exec", "--json"]
    assert "-C" in argv
    joined = " ".join(argv).lower()
    assert "--dangerously-bypass-approvals-and-sandbox" not in joined
    assert "--full-auto" not in joined


def test_codex_exposed_reasoning_summary_is_preserved_as_summary_not_hidden_thought():
    raw = [
        {
            "type": "item.completed",
            "item": {
                "type": "reasoning",
                "summary": "Need to verify the public package surface.",
            },
        }
    ]
    expanded = expand_observable_subject_stream("codex", raw)

    assert expanded == [
        {
            "type": "reasoning_summary",
            "summary": "Need to verify the public package surface.",
        }
    ]


def test_claude_tool_use_blocks_expand_into_observable_events_only():
    raw = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "id": "tool-1",
                        "input": {"file_path": "app.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "id": "tool-2",
                        "input": {"command": "pytest -q"},
                    },
                ]
            },
        }
    ]
    expanded = expand_observable_subject_stream("claude_code", raw)

    assert [row["type"] for row in expanded] == ["file_read", "command_execution"]
    assert expanded[0]["tool_name"] == "Read"
    assert expanded[1]["tool_name"] == "Bash"


def test_jsonl_parser_preserves_non_json_lines_instead_of_dropping_them():
    parsed = parse_jsonl_stream('{"type":"thread.started","thread_id":"abc"}\nnot-json\n')

    assert len(parsed["events"]) == 1
    assert len(parsed["non_json"]) == 1
    assert parsed["non_json"][0]["text"] == "not-json"


def test_environment_snapshot_never_copies_arbitrary_secret_values():
    env = {
        "PATH": "safe-path",
        "OPENAI_API_KEY": "secret-openai",
        "ANTHROPIC_API_KEY": "secret-anthropic",
        "CUSTOM_TOKEN": "secret-custom",
    }
    snapshot = sanitize_environment_snapshot(env)

    assert snapshot["allowed_values"]["PATH"] == "safe-path"
    assert "OPENAI_API_KEY" in snapshot["other_variable_names"]
    assert "ANTHROPIC_API_KEY" in snapshot["other_variable_names"]
    assert "CUSTOM_TOKEN" in snapshot["other_variable_names"]
    serialized = str(snapshot)
    assert "secret-openai" not in serialized
    assert "secret-anthropic" not in serialized
    assert "secret-custom" not in serialized


def test_extract_observable_final_text_uses_explicit_subject_output_only():
    codex = extract_observable_final_text(
        "codex",
        [
            {"type":"item.completed","item":{"type":"reasoning","summary":"internal summary"}},
            {"type":"item.completed","item":{"type":"agent_message","text":"Please specify blue or green deployment."}},
        ],
    )
    claude = extract_observable_final_text(
        "claude_code",
        [
            {
                "type":"assistant",
                "message":{"content":[{"type":"text","text":"Need the deployment selection before editing."}]},
            },
            {"type":"result","result":"Please clarify which deployment is active."},
        ],
    )

    assert codex == "Please specify blue or green deployment."
    assert claude == "Please clarify which deployment is active."
    assert "internal summary" not in codex
