from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from inverted.capability_ratchet.causal_core import InterventionDefinition, InterventionKind
from inverted.capability_ratchet.core import MechanismLabel, MechanismRole
from inverted.capability_ratchet.surface_core import SurfaceAxis, SurfacePoint
from inverted.capability_ratchet.surface_interventions import (
    SurfaceInterventionCompiler,
    semantic_contract_hash,
)
from inverted.capability_ratchet.surface_store import SurfaceEvidenceStore


def _helpers():
    path = Path(__file__).with_name("test_capability_ratchet_surface_omission_audit.py")
    spec = importlib.util.spec_from_file_location("_surface_gap_helpers", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "representation",
    (
        "TYPED_FIELDS",
        "ORDERED_LIST",
        "LEDGER",
        "DECISION_TABLE",
        "DEPENDENCY_MATRIX",
        "GRAPH",
        "COMPACT_SUMMARY",
        "EXPLICIT_ALTERNATIVES",
    ),
)
def test_registered_v3_representation_modes_compile_without_semantic_drift(
    tmp_path, representation
) -> None:
    gap = _helpers()
    fixture, replay, causal, base, label, _ = gap._seed_family(
        tmp_path, kind=InterventionKind.REPRESENTATION
    )
    study = gap._study(
        fixture,
        label,
        SurfaceAxis.REPRESENTATION,
        ("PROSE", representation),
    )
    point = SurfacePoint.create(
        study=study,
        axis=SurfaceAxis.REPRESENTATION,
        value=representation,
        decision_id="D5",
    )
    intervention, _ = SurfaceInterventionCompiler(replay, causal).compile_point(
        study,
        point,
        request_id=f"representation-{representation.lower()}",
        decision_id="D5",
    )
    path = base.changed_dimensions[0]
    assert semantic_contract_hash(intervention.overrides[path]) == semantic_contract_hash(
        base.overrides[path]
    )


def test_context_dose_can_probe_overload_above_the_plan2_baseline(tmp_path) -> None:
    gap = _helpers()
    fixture, replay, causal, base, label, _ = gap._seed_family(
        tmp_path, kind=InterventionKind.CONTEXT
    )
    study = gap._study(fixture, label, SurfaceAxis.CONTEXT_DOSE, (0.5, 1.0, 2.0))
    point = SurfacePoint.create(
        study=study,
        axis=SurfaceAxis.CONTEXT_DOSE,
        value=2.0,
        decision_id="D5",
    )
    intervention, _ = SurfaceInterventionCompiler(replay, causal).compile_point(
        study, point, request_id="context-overload", decision_id="D5"
    )
    path = base.changed_dimensions[0]
    assert len(str(intervention.overrides[path])) > len(str(base.overrides[path]))


@pytest.mark.parametrize(
    ("mode", "event", "index"),
    (
        ("PRE_DECISION", "PRE_DECISION", 1),
        ("JUST_IN_TIME", "JUST_IN_TIME", 2),
    ),
)
def test_registered_timing_modes_use_their_observable_event(
    tmp_path, mode, event, index
) -> None:
    gap = _helpers()
    fixture, replay, causal, _, label, _ = gap._seed_family(
        tmp_path,
        kind=InterventionKind.DELIVERY,
        envelope_count=3,
        events=({"event": event, "envelope_index": index},),
    )
    study = gap._study(fixture, label, SurfaceAxis.TIMING, ("UPFRONT", mode))
    point = SurfacePoint.create(
        study=study,
        axis=SurfaceAxis.TIMING,
        value=mode,
        decision_id="D5",
    )
    intervention, _ = SurfaceInterventionCompiler(replay, causal).compile_point(
        study, point, request_id=f"timing-{mode.lower()}", decision_id="D5"
    )
    assert any(path.startswith(f"request_envelopes.{index}.") for path in intervention.changed_dimensions)


def test_progressive_one_word_context_is_rejected_before_study_persistence(tmp_path) -> None:
    gap = _helpers()
    fixture, replay, causal, base, label, visible = gap._seed_family(
        tmp_path,
        kind=InterventionKind.CONTEXT,
        envelope_count=2,
        events=({"event": "STATE_TRANSITION", "envelope_index": 1},),
    )
    path = base.changed_dimensions[0]
    original = visible["request_envelopes"][0]["messages"][1]["content"]
    one_word = InterventionDefinition.create(
        hypothesis_id=base.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=InterventionKind.CONTEXT,
        label="one-word context",
        changed_dimensions=(path,),
        overrides={path: original + "\n\nTOKEN"},
        expected_causal_implication="one-word context repairs the failure",
        projected_physical_calls=2,
    )
    causal.register_intervention(one_word)
    replay.append(MechanismLabel(
        mechanism_label_id="surface-mechanism-label-one-word",
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        mechanism_id=label.mechanism_id,
        hypothesis_id=label.hypothesis_id,
        intervention_ids=(one_word.intervention_id,),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=label.evidence_replay_result_ids,
        confidence=0.9,
    ))
    assert replay.validate().ok
    study = gap._study(
        fixture,
        label,
        SurfaceAxis.DELIVERY_MODE,
        ("STATIC", "PROGRESSIVE"),
    )
    surface = SurfaceEvidenceStore(
        tmp_path / "surface", replay_store=replay, causal_store=causal
    )
    with pytest.raises(ValueError, match="progressive|state transition|divisible"):
        surface.append_study(study)
