from __future__ import annotations

from inverted.assistant_value.coding_tomography import (
    COMPOUNDS,
    MECHANISMS,
    PATHOLOGIES,
    compound_ablations,
    detect_stuck_loops,
    first_divergence,
    mechanism_registry,
    normalize_events,
    pathology_registry,
    trajectory_metrics,
)


def test_registry_has_full_mechanism_and_frontier_pathology_floor():
    mechanisms = mechanism_registry()
    pathologies = pathology_registry()

    assert len(MECHANISMS) == 40
    assert len(PATHOLOGIES) == 40
    assert len(COMPOUNDS) >= 5
    assert len(mechanisms["mechanisms"]) == 40
    assert len(pathologies["pathologies"]) == 40
    assert {"P7", "P8", "P9", "P10"}.issubset(
        {row["level"] for row in pathologies["pathologies"]}
    )


def test_every_compound_has_one_factor_ablation_for_every_component():
    for compound in COMPOUNDS:
        rows = compound_ablations(compound)
        assert len(rows) == len(compound["components"])
        removed = {row["removed_component"] for row in rows}
        assert removed == set(compound["components"])
        for row in rows:
            assert row["removed_component"] not in row["active_components"]


def test_unknown_native_event_stays_unknown_instead_of_being_invented():
    events = normalize_events("codex", [{"type": "mystery.internal.thing", "foo": 1}])
    assert events[0]["event_type"] == "UNKNOWN"
    assert events[0]["observable"] is True


def test_command_event_is_reclassified_only_from_observable_command_content():
    events = normalize_events(
        "codex",
        [
            {"type": "command_execution", "command": "python -m pytest -q"},
            {"type": "command_execution", "command": "git status"},
        ],
    )
    assert events[0]["event_type"] == "TEST"
    assert events[1]["event_type"] == "COMMAND"


def test_first_divergence_identifies_first_observable_behavioral_split():
    success = [
        {"event_type": "SEARCH", "raw_ref": "s1"},
        {"event_type": "FILE_READ", "raw_ref": "s2"},
        {"event_type": "VERIFY", "raw_ref": "s3"},
    ]
    failure = [
        {"event_type": "SEARCH", "raw_ref": "f1"},
        {"event_type": "FILE_EDIT", "raw_ref": "f2"},
        {"event_type": "VERIFY", "raw_ref": "f3"},
    ]

    result = first_divergence(success, failure)

    assert result["diverged"] is True
    assert result["index"] == 1
    assert result["success_event"] == "FILE_READ"
    assert result["failed_event"] == "FILE_EDIT"


def test_stuck_loop_detection_finds_repeated_repair_cycles():
    events = []
    seq = ["FILE_EDIT", "TEST", "TOOL_ERROR", "REPAIR"] * 4
    for index, event_type in enumerate(seq, start=1):
        events.append({"sequence": index, "event_type": event_type})

    loops = detect_stuck_loops(events, repeat_threshold=3)

    assert loops
    assert any(loop["repeats"] >= 3 for loop in loops)


def test_trajectory_metrics_requires_verification_after_last_edit():
    events = [
        {"event_type": "SEARCH"},
        {"event_type": "FILE_READ"},
        {"event_type": "FILE_EDIT"},
        {"event_type": "TEST"},
        {"event_type": "FILE_EDIT"},
        {"event_type": "FINAL_RESPONSE"},
        {"event_type": "SESSION_STOP"},
    ]
    metrics = trajectory_metrics(events, oracle_success=False)

    assert metrics["first_edit"] == 3
    assert metrics["last_edit"] == 5
    assert metrics["last_verify"] == 4
    assert metrics["verification_after_last_edit"] is False
    assert metrics["oracle_success"] is False
