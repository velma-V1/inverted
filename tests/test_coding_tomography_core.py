from __future__ import annotations

from inverted.assistant_value.coding_tomography import (
    COMPOUNDS,
    MECHANISMS,
    PATHOLOGIES,
    classify_mechanism_evidence,
    compound_ablations,
    detect_stuck_loops,
    first_divergence,
    mechanism_observable_signal,
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


def test_null_intervention_is_not_mislabeled_causal():
    result = classify_mechanism_evidence(
        observed_trials=6,
        independent_tasks=3,
        causal_interventions=4,
        generalized_families=2,
        rescue_rate=0.0,
        regression_rate=0.0,
        complexity_units=1.0,
    )

    assert result["status"] == "REPLICATED"
    assert result["implementation_decision"] == "UNKNOWN"
    assert result["net_effect"] == 0.0


def test_negative_causal_effect_is_rejected_before_generalization_promotion():
    result = classify_mechanism_evidence(
        observed_trials=8,
        independent_tasks=4,
        causal_interventions=4,
        generalized_families=3,
        rescue_rate=0.0,
        regression_rate=0.5,
        complexity_units=1.0,
    )

    assert result["status"] == "REJECT"
    assert result["implementation_decision"] == "REJECT"
    assert result["net_effect"] < 0.0


def test_positive_matched_effect_can_be_causal_but_not_high_value_without_cost_evidence():
    result = classify_mechanism_evidence(
        observed_trials=8,
        independent_tasks=4,
        causal_interventions=4,
        generalized_families=1,
        rescue_rate=0.5,
        regression_rate=0.0,
        complexity_units=None,
    )

    assert result["status"] == "CAUSAL"
    assert result["implementation_decision"] == "CLONE_CANDIDATE"
    assert result["complexity_units"] is None


def test_looked_at_without_observable_signal_stays_unknown():
    result = classify_mechanism_evidence(
        opportunity_trials=6,
        observed_trials=0,
        independent_tasks=0,
        causal_interventions=0,
        generalized_families=0,
        rescue_rate=0.0,
        regression_rate=0.0,
        complexity_units=None,
    )
    assert result["status"] == "UNKNOWN"
    assert result["implementation_decision"] == "UNKNOWN"


def test_one_directional_intervention_is_not_enough_for_causal_label():
    result = classify_mechanism_evidence(
        opportunity_trials=6,
        observed_trials=4,
        independent_tasks=3,
        causal_interventions=1,
        generalized_families=1,
        rescue_rate=1.0,
        regression_rate=0.0,
        complexity_units=None,
    )
    assert result["status"] == "REPLICATED"
    assert result["implementation_decision"] == "MODIFY_CANDIDATE"


def test_observable_signal_uses_trajectory_not_task_intent():
    quiet = [
        {"event_type":"SESSION_START","observable_fields":{}},
        {"event_type":"FINAL_RESPONSE","observable_fields":{}},
        {"event_type":"SESSION_STOP","observable_fields":{}},
    ]
    searched = [
        {"event_type":"SEARCH","observable_fields":{"command":"rg target"}},
        {"event_type":"FILE_READ","observable_fields":{"path":"app.py"}},
        {"event_type":"FILE_READ","observable_fields":{"path":"policy.py"}},
    ]
    assert mechanism_observable_signal("M02", quiet, {}) is False
    assert mechanism_observable_signal("M02", searched, {}) is True


def test_normalized_event_retains_safe_observable_command_details():
    event = normalize_events(
        "codex",
        [{"type":"command_execution","command":"pytest -q","cwd":"repo","exit_code":1}],
    )[0]
    assert event["event_type"] == "TEST"
    assert event["observable_fields"]["command"] == "pytest -q"
    assert event["observable_fields"]["cwd"] == "repo"
    assert event["observable_fields"]["exit_code"] == 1
