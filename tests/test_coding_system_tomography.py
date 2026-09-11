from __future__ import annotations

from pathlib import Path

from inverted.assistant_value.coding_subjects import (
    build_claude_code_command,
    build_codex_command,
    expand_observable_subject_event,
    extract_subject_session_id,
    parse_jsonl_stream,
)
from inverted.assistant_value.coding_tomography import (
    COMPOUNDS,
    MECHANISMS,
    PATHOLOGIES,
    classify_mechanism_evidence,
    compound_ablations,
    detect_stuck_loops,
    first_divergence,
    normalize_events,
    pathology_registry,
    trajectory_metrics,
)


def test_registry_has_40_mechanisms_and_40_frontier_pathologies():
    assert len(MECHANISMS) == 40
    assert len(PATHOLOGIES) == 40
    assert len(COMPOUNDS) >= 5
    registry = pathology_registry()
    assert registry["ladder"][-1] == "P10"


def test_every_compound_has_single_component_ablations():
    for compound in COMPOUNDS:
        rows = compound_ablations(compound)
        assert len(rows) == len(compound["components"])
        assert {row["removed_component"] for row in rows} == set(compound["components"])
        assert all(len(row["active_components"]) == len(compound["components"]) - 1 for row in rows)


def test_codex_command_uses_exec_json_and_explicit_cwd(tmp_path: Path):
    cmd = build_codex_command(prompt="fix it", cwd=tmp_path)
    assert cmd.argv[:3] == ("codex","exec","--json")
    assert "-C" in cmd.argv
    assert str(tmp_path) in cmd.argv
    assert cmd.argv[-1] == "fix it"


def test_claude_command_uses_print_stream_json_verbose(tmp_path: Path):
    cmd = build_claude_code_command(prompt="fix it", cwd=tmp_path)
    assert cmd.argv[:3] == ("claude","-p","fix it")
    assert "--output-format" in cmd.argv
    assert "stream-json" in cmd.argv
    assert "--verbose" in cmd.argv


def test_parse_jsonl_preserves_unparseable_lines():
    parsed = parse_jsonl_stream('{"type":"thread.started","thread_id":"abc"}\nnot-json\n')
    assert len(parsed["events"]) == 1
    assert len(parsed["non_json"]) == 1
    assert extract_subject_session_id("codex", parsed["events"]) == "abc"


def test_codex_observable_reasoning_is_summary_not_hidden_content():
    raw = {
        "type":"item.completed",
        "item":{"type":"reasoning","text":"safe summary","content":"hidden raw"},
    }
    expanded = expand_observable_subject_event("codex", raw)
    assert expanded == [{"type":"reasoning_summary","summary":"safe summary"}]
    assert "hidden raw" not in str(expanded)


def test_claude_tool_use_blocks_expand_to_observable_actions():
    raw = {
        "type":"assistant",
        "message":{
            "content":[
                {"type":"tool_use","id":"a","name":"Read","input":{"file_path":"x.py"}},
                {"type":"tool_use","id":"b","name":"Bash","input":{"command":"pytest -q"}},
            ]
        },
    }
    expanded = expand_observable_subject_event("claude_code", raw)
    assert [row["type"] for row in expanded] == ["file_read","command_execution"]
    normalized = normalize_events("claude_code", expanded)
    assert [row["event_type"] for row in normalized] == ["FILE_READ","TEST"]


def test_first_divergence_and_stuck_loop_are_observable_only():
    good = normalize_events("codex", [
        {"type":"search"},
        {"type":"file_read"},
        {"type":"file_change"},
        {"type":"test"},
    ])
    bad = normalize_events("codex", [
        {"type":"search"},
        {"type":"file_read"},
        {"type":"command"},
        {"type":"command"},
        {"type":"command"},
        {"type":"command"},
    ])
    div = first_divergence(good, bad)
    assert div["diverged"] is True
    assert div["index"] == 2
    loops = detect_stuck_loops(bad, repeat_threshold=3)
    assert loops
    assert loops[0]["pattern"] == ["COMMAND"]


def test_trajectory_metrics_require_verification_after_edit():
    events = normalize_events("codex", [
        {"type":"search"},
        {"type":"file_change"},
        {"type":"command_execution","command":"pytest -q"},
        {"type":"agent_message"},
    ])
    metrics = trajectory_metrics(events, oracle_success=True)
    assert metrics["verification_after_last_edit"] is True
    assert metrics["first_edit"] == 2
    assert metrics["first_test"] == 3


def test_mechanism_gate_does_not_call_one_observation_clone_ready():
    weak = classify_mechanism_evidence(
        observed_trials=1,
        independent_tasks=1,
        causal_interventions=0,
        generalized_families=1,
        rescue_rate=1.0,
        regression_rate=0.0,
        complexity_units=1,
    )
    assert weak["status"] == "OBSERVED"
    assert weak["implementation_decision"] == "MODIFY_CANDIDATE"

    strong = classify_mechanism_evidence(
        observed_trials=20,
        independent_tasks=5,
        causal_interventions=3,
        generalized_families=3,
        rescue_rate=0.50,
        regression_rate=0.05,
        complexity_units=2,
    )
    assert strong["status"] == "HIGH_VALUE"
    assert strong["implementation_decision"] == "CLONE_CANDIDATE"
