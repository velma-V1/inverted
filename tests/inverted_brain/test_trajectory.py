from inverted_brain.trajectory import normalize_qwen, normalize_claude, normalize_codex


def test_equivalent_shell_mutations_normalize_equally():
    q = [{"event":"model_action","step":1,"action":{"type":"shell","command":"printf x > a.txt"}}]
    c = [{"type":"assistant","uuid":"c1","message":{"content":[{"type":"tool_use","name":"mcp__arena__shell","input":{"command":"printf x > a.txt"}}]}}]
    x = [{"type":"item.started","item":{"id":"x1","type":"mcp_tool_call","arguments":{"command":"printf x > a.txt"}}}]
    assert normalize_qwen(q)[0].kind == "mutation"
    assert normalize_claude(c)[0].kind == "mutation"
    assert normalize_codex(x)[0].kind == "mutation"


def test_post_mutation_read_is_state_reread():
    raw = [
        {"event":"model_action","step":1,"action":{"type":"shell","command":"printf x > a.txt"}},
        {"event":"model_action","step":2,"action":{"type":"shell","command":"cat a.txt"}},
    ]
    events = normalize_qwen(raw)
    assert [e.kind for e in events] == ["mutation", "state_reread"]


def test_source_links_are_preserved():
    raw = [{"type":"item.started","item":{"id":"tool-7","type":"mcp_tool_call","arguments":{"command":"cat config.json"}}}]
    event = normalize_codex(raw)[0]
    assert event.source_id == "tool-7"
    assert event.data["item"]["id"] == "tool-7"
