from __future__ import annotations

import json
from pathlib import Path

from inverted.system_testing import load_system_template
from inverted.system_testing.planner import (
    ComparisonKind,
    build_factorial_core,
    plan_template_comparisons,
)


def _write(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _base(system_id: str, factors: list[str], mechanisms: list[dict], interactions=None):
    return {
        "schema_version": 1,
        "template_id": f"{system_id.lower()}-v1",
        "system_id": system_id,
        "decision_id": f"DECIDE-{system_id}",
        "description": f"Template for {system_id}.",
        "factors": factors,
        "mechanisms": mechanisms,
        "interactions": interactions or [],        "task_families": ["state"],
        "operating_regions": ["GLOBAL_INTERACTION"],
        "primary_metrics": ["verified_success"],
        "hard_gates": ["no_catastrophic_regression"],
        "evidence_fields": ["active_mechanisms", "verified_outcome"],
        "allowed_dispositions": [
            "REQUIRED", "CONDITIONAL", "REDUNDANT", "HARMFUL", "UNRESOLVED"
        ],
    }


def _mechanism(mid: str, *, isolate: bool, ablate: bool) -> dict:
    return {
        "mechanism_id": mid,
        "decision_id": f"DECIDE-{mid}",
        "description": f"Mechanism {mid}.",
        "owner": "SYSTEM",
        "responsibilities": [f"RESP_{mid}"],
        "expected_role": "causal support",
        "isolation_required": isolate,
        "ablation_required": ablate,
    }


def _load(tmp_path: Path, name: str, data: dict):
    return load_system_template(_write(tmp_path, name, data))

def test_plan_template_generates_only_decision_relevant_comparisons(tmp_path):
    data = _base(
        "TEST",
        ["TEST_FACTOR"],
        [_mechanism("M1", isolate=True, ablate=True), _mechanism("M2", isolate=False, ablate=True)],
        [{
            "probe_id": "M1_X_M2",
            "members": ["M1", "M2"],
            "decision_id": "DECIDE-M1-X-M2",
            "reason": "Test interaction.",
        }],
    )
    template = _load(tmp_path, "test.json", data)

    plan = plan_template_comparisons(template)

    assert [c.kind for c in plan.comparisons] == [
        ComparisonKind.FULL_VS_RAW,
        ComparisonKind.ISOLATION,
        ComparisonKind.ABLATION,
        ComparisonKind.ABLATION,
        ComparisonKind.INTERACTION,
    ]
    assert plan.comparison_count == 5
    assert plan.condition_count == 12
    assert all(c.decision_id for c in plan.comparisons)
    interaction = plan.comparisons[-1]
    assert interaction.decision_id == "DECIDE-M1-X-M2"
    assert [cell.active_mechanisms for cell in interaction.cells] == [
        (), ("M1",), ("M2",), ("M1", "M2")
    ]


def test_raw_template_generates_no_internal_comparisons(tmp_path):
    raw = _base("RAW", [], [])
    template = _load(tmp_path, "raw.json", raw)

    plan = plan_template_comparisons(template)

    assert plan.comparison_count == 0
    assert plan.condition_count == 0


def test_planner_is_deterministic_under_mechanism_input_order(tmp_path):
    m1 = _mechanism("M1", isolate=True, ablate=True)
    m2 = _mechanism("M2", isolate=True, ablate=True)
    one = _load(tmp_path, "one.json", _base("TEST", ["X"], [m2, m1]))
    two = _load(tmp_path, "two.json", _base("TEST", ["X"], [m1, m2]))

    assert plan_template_comparisons(one) == plan_template_comparisons(two)

def test_factorial_core_freezes_raw_brain_inverted_and_combined_cells(tmp_path):
    raw = _load(tmp_path, "raw.json", _base("RAW", [], []))
    brain = _load(
        tmp_path,
        "brain.json",
        _base("BRAIN", ["BRAIN"], [_mechanism("B1", isolate=True, ablate=True)]),
    )
    inverted = _load(
        tmp_path,
        "inverted.json",
        _base("INVERTED_SYSTEM", ["INVERTED"], [_mechanism("I1", isolate=True, ablate=True)]),
    )
    combined = _load(
        tmp_path,
        "combined.json",
        _base(
            "BRAIN_INVERTED",
            ["BRAIN", "INVERTED"],
            [
                _mechanism("B1", isolate=True, ablate=True),
                _mechanism("I1", isolate=True, ablate=True),
            ],
        ),
    )

    core = build_factorial_core((combined, raw, inverted, brain))

    assert core.kind is ComparisonKind.FACTORIAL_CORE
    assert core.decision_id == "DECIDE-BRAIN-X-INVERTED"
    assert [cell.system_id for cell in core.cells] == [
        "RAW", "BRAIN", "INVERTED_SYSTEM", "BRAIN_INVERTED"
    ]
    assert [cell.factors for cell in core.cells] == [
        (), ("BRAIN",), ("INVERTED",), ("BRAIN", "INVERTED")
    ]