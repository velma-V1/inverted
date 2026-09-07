from __future__ import annotations

from pathlib import Path

from inverted.system_testing import ResponsibilityOwner, load_system_template
from inverted.system_testing.planner import build_factorial_core


ROOT = Path("configs/system-tests")
FILES = {
    "RAW": ROOT / "raw.json",
    "BRAIN": ROOT / "brain.json",
    "INVERTED_SYSTEM": ROOT / "inverted-system.json",
    "BRAIN_INVERTED": ROOT / "brain-inverted.json",
}


def _load_all():
    return {system_id: load_system_template(path) for system_id, path in FILES.items()}


def test_initial_profiles_form_exact_two_by_two_core():
    templates = _load_all()

    assert templates["RAW"].factors == ()
    assert templates["BRAIN"].factors == ("BRAIN",)
    assert templates["INVERTED_SYSTEM"].factors == ("INVERTED",)
    assert templates["BRAIN_INVERTED"].factors == ("BRAIN", "INVERTED")

    core = build_factorial_core(templates.values())
    assert len(core.cells) == 4

def test_combined_profile_is_exact_union_of_brain_and_inverted_mechanisms():
    templates = _load_all()
    brain = set(templates["BRAIN"].mechanism_ids)
    inverted = set(templates["INVERTED_SYSTEM"].mechanism_ids)
    combined = set(templates["BRAIN_INVERTED"].mechanism_ids)

    assert brain
    assert inverted
    assert brain.isdisjoint(inverted)
    assert combined == brain | inverted


def test_raw_profile_contains_no_support_mechanisms():
    raw = _load_all()["RAW"]
    assert raw.mechanism_ids == ()


def test_inverted_protected_responsibilities_are_system_owned():
    inverted = _load_all()["INVERTED_SYSTEM"]
    by_id = {mechanism.mechanism_id: mechanism for mechanism in inverted.mechanisms}

    assert by_id["INV_STATE_INVARIANTS"].owner is ResponsibilityOwner.KERNEL
    assert "CANONICAL_STATE" in by_id["INV_STATE_INVARIANTS"].responsibilities
    assert "INVARIANTS" in by_id["INV_STATE_INVARIANTS"].responsibilities
    assert by_id["INV_INDEPENDENT_VERIFICATION"].owner is ResponsibilityOwner.VERIFIER
    assert by_id["INV_COMMIT_RECOVERY_FENCE"].owner is ResponsibilityOwner.KERNEL