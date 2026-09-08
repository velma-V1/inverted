from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from inverted.capability_ratchet import cli
from inverted.capability_ratchet.core import Partition, PromotionState
from inverted.capability_ratchet.query import select_surface_study
from inverted.capability_ratchet.surface_core import SurfaceAxis, SurfacePoint, SurfaceStudy
from inverted.capability_ratchet.surface_planner import SurfacePlan


STATE = "a" * 64


def _study(*, mechanism_id="mechanism-1", failure_id="failure-1") -> SurfaceStudy:
    return SurfaceStudy.create(
        failure_snapshot_id=failure_id,
        mechanism_id=mechanism_id,
        parent_state_hash=STATE,
        partition=Partition.DEVELOPMENT,
        promotion_state=PromotionState.MOVEMENT,
        decision_id="D3",
        axes=(SurfaceAxis.REASONING_BUDGET,),
        axis_values={"REASONING_BUDGET": (0, 512, 8192)},
    )


class FakeSurfaceStore:
    def __init__(self, studies):
        self._studies = tuple(studies)

    def studies(self, mechanism_id=None):
        rows = self._studies
        if mechanism_id is not None:
            rows = tuple(row for row in rows if row.mechanism_id == mechanism_id)
        return rows

    def observations(self, study_id=None):
        return ()

    def profiles(self, mechanism_id=None):
        return ()

    def validate(self):
        return SimpleNamespace(ok=True)


class FakeSurfaceLab:
    def __init__(self, study):
        self.study = study
        self.surface_store = FakeSurfaceStore((study,))

    def prepare(self, study_id, *, max_new_points=2):
        assert study_id == self.study.study_id
        point = SurfacePoint.create(
            study=self.study,
            axis=SurfaceAxis.REASONING_BUDGET,
            value=8192,
            decision_id="D3",
            protected_exploration=True,
        )
        return SurfacePlan(
            points=(point,),
            decision_reason="D3 upper harm boundary remains unresolved",
            minimum_physical_calls=1,
            expected_physical_calls=1,
            worst_case_physical_calls=1,
            protected_exploration_calls=1,
        )


def test_surface_study_selection_is_exact_and_rejects_ambiguity() -> None:
    first = _study()
    second = _study(failure_id="failure-2")
    store = FakeSurfaceStore((first, second))

    assert select_surface_study(store, study_id=first.study_id) == first
    with pytest.raises(ValueError, match="ambiguous|multiple"):
        select_surface_study(store, mechanism_id="mechanism-1")
    with pytest.raises(ValueError, match="exactly one|selector"):
        select_surface_study(store)


def test_plan_surface_is_zero_call_and_exposes_call_geometry(tmp_path, monkeypatch, capsys) -> None:
    study = _study()
    lab = FakeSurfaceLab(study)
    monkeypatch.setattr(cli, "_build_surface_lab", lambda store, causal_root, surface_root: lab)

    code = cli.main([
        "plan-surface",
        "--replay-root", str(tmp_path / "replay"),
        "--causal-root", str(tmp_path / "causal"),
        "--surface-root", str(tmp_path / "surface"),
        "--study-id", study.study_id,
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["study_id"] == study.study_id
    assert payload["points"][0]["value"] == 8192
    assert payload["call_geometry"] == {
        "minimum": 1,
        "expected": 1,
        "worst_case": 1,
        "protected_exploration": 1,
    }


def test_show_surface_is_zero_call_and_reports_integrity(tmp_path, monkeypatch, capsys) -> None:
    study = _study()
    lab = FakeSurfaceLab(study)
    monkeypatch.setattr(cli, "_build_surface_lab", lambda store, causal_root, surface_root: lab)

    code = cli.main([
        "show-surface",
        "--replay-root", str(tmp_path / "replay"),
        "--causal-root", str(tmp_path / "causal"),
        "--surface-root", str(tmp_path / "surface"),
        "--mechanism-id", study.mechanism_id,
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["study"]["study_id"] == study.study_id
    assert payload["surface_store_valid"] is True


def test_run_surface_rejects_before_live_executor_without_explicit_gate(tmp_path, capsys) -> None:
    invoked = []

    def forbidden(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("live surface executor must not be reached without gate")

    code = cli.main([
        "run-surface",
        "--replay-root", str(tmp_path / "replay"),
        "--causal-root", str(tmp_path / "causal"),
        "--surface-root", str(tmp_path / "surface"),
        "--study-id", "surface-study-1",
    ], live_surface_executor=forbidden)
    captured = capsys.readouterr()
    assert code == 2
    assert "--allow-model-calls" in captured.err
    assert invoked == []


def test_run_surface_uses_injected_executor_only_after_explicit_gate(tmp_path, capsys) -> None:
    invoked = []

    def fake_runner(store, causal_root, surface_root, args):
        invoked.append(args.study_id)
        return {"study_id": args.study_id, "MODEL_CALLS": 1}

    code = cli.main([
        "run-surface",
        "--replay-root", str(tmp_path / "replay"),
        "--causal-root", str(tmp_path / "causal"),
        "--surface-root", str(tmp_path / "surface"),
        "--study-id", "surface-study-1",
        "--allow-model-calls",
    ], live_surface_executor=fake_runner)
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["MODEL_CALLS"] == 1
    assert invoked == ["surface-study-1"]
