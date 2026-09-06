from collections import Counter
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from inverted.harvest_d.hd_next2.cases import OPERATING_REGIONS, generate_hd_next2_cases
from inverted.harvest_d.hd_next2.config import load_hd_next2_config
from inverted.harvest_d.hd_next2.stages import A0_TREATMENT_SPECS, build_stage_plans
from inverted.harvest_d.hd_next2.types import StageId


CONFIG = Path("configs/harvest-d-hd-next-2a.json")


def _a0_plan():
    config = load_hd_next2_config(CONFIG)
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    plans = build_stage_plans(StageId.A0, config, cases, {}, {}, {})
    assert len(plans) == 1
    return plans[0]


def test_a0_freezes_exactly_192_calls_and_64_per_model():
    plan = _a0_plan()
    assert len(plan.units) == 192
    assert Counter(unit.model_key for unit in plan.units) == {
        "SMALL_A": 64,
        "QWEN": 64,
        "DEVSTRAL_24B": 64,
    }
    assert plan.forecast_combined_actions == 232
    assert plan.forecast_combined_actions <= 1000


def test_a0_covers_every_region_with_four_exact_replications_per_cell():
    plan = _a0_plan()
    assert {unit.operating_region for unit in plan.units} == set(OPERATING_REGIONS)
    cells = Counter(
        (unit.model_key, unit.case_id, unit.operating_region, unit.treatment_kind)
        for unit in plan.units
    )
    assert len(cells) == 48
    assert set(cells.values()) == {4}
    assert {
        unit.replicate for unit in plan.units
        if (unit.model_key, unit.case_id, unit.operating_region, unit.treatment_kind)
        == next(iter(cells))
    } == {1, 2, 3, 4}


def test_a0_uses_only_development_anchors_and_same_cases_for_both_treatments():
    plan = _a0_plan()
    assert all(unit.partition == "development" for unit in plan.units)
    assert not any(unit.partition in {"fresh", "sealed"} for unit in plan.units)
    for model in ("SMALL_A", "QWEN", "DEVSTRAL_24B"):
        raw = {unit.case_id for unit in plan.units if unit.model_key == model and unit.treatment_kind == "RAW"}
        historical = {unit.case_id for unit in plan.units if unit.model_key == model and unit.treatment_kind == "HISTORICAL_SEED"}
        assert raw == historical
        assert len(raw) == 8


def test_a0_replay_freezes_identity_and_execution_metadata():
    first = _a0_plan()
    second = _a0_plan()
    assert first == second
    assert len({unit.unit_id for unit in first.units}) == 192
    assert [unit.execution_position for unit in first.units] == list(range(1, 193))
    assert all(unit.selection_reason for unit in first.units)
    assert all(unit.model_block for unit in first.units)


def test_a0_reordered_exact_canonical_cases_produce_identical_schedule():
    config = load_hd_next2_config(CONFIG)
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    forward, = build_stage_plans(StageId.A0, config, cases, {}, {}, {})
    reverse, = build_stage_plans(StageId.A0, config, reversed(cases), {}, {}, {})
    assert reverse == forward


def test_a0_reordered_model_mapping_produces_identical_canonical_schedule():
    config = load_hd_next2_config(CONFIG)
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    canonical, = build_stage_plans(StageId.A0, config, cases, {}, {}, {})
    config["models"] = {
        "DEVSTRAL_24B": config["models"]["DEVSTRAL_24B"],
        "QWEN": config["models"]["QWEN"],
        "SMALL_A": config["models"]["SMALL_A"],
    }

    reordered, = build_stage_plans(StageId.A0, config, cases, {}, {}, {})

    assert reordered == canonical


@pytest.mark.parametrize(
    ('section', 'field', 'value'),
    [
        ('a0', 'treatment_kinds', ['HISTORICAL_SEED', 'RAW']),
        ('a0', 'replications_per_cell', 3),
        ('a0', 'diagnostic_model', 'QWEN'),
        ('a0', 'non_model_action_forecast', 41),
        ('models', 'QWEN', 'forged-model-id'),
    ],
)
def test_a0_rejects_post_load_mutation_of_frozen_planner_inputs(section, field, value):
    config = load_hd_next2_config(CONFIG)
    cases = generate_hd_next2_cases('development', seed=20260921, per_region=1)
    config[section][field] = value

    with pytest.raises(ValueError, match='frozen A0 planner configuration'):
        build_stage_plans(StageId.A0, config, cases, {}, {}, {})

@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "spoofed_id", "spoofed_region", "spoofed_partition"])
def test_a0_rejects_any_noncanonical_case_collection(mutation):
    config = load_hd_next2_config(CONFIG)
    canonical = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    cases = list(canonical)
    if mutation == "missing":
        cases.pop()
    elif mutation == "duplicate":
        cases[-1] = cases[0]
    elif mutation == "extra":
        cases.append(canonical[0])
    elif mutation == "spoofed_id":
        cases[0] = replace(cases[0], case_id=cases[0].case_id + "-20260921")
    else:
        metadata = dict(cases[0].metadata)
        metadata["hd_next2_region" if mutation == "spoofed_region" else "partition"] = (
            "TRANSACTION" if mutation == "spoofed_region" else "fresh"
        )
        cases[0] = replace(cases[0], metadata=metadata)
    with pytest.raises(ValueError, match="exact canonical"):
        build_stage_plans(StageId.A0, config, cases, {}, {}, {})


def test_a0_units_bind_frozen_treatment_specs_and_explicit_model_roles():
    plan = _a0_plan()
    bindings = {(u.treatment_kind, u.treatment_spec_id, u.treatment_spec_sha256) for u in plan.units}
    assert len(bindings) == 2
    assert all(len(sha) == 64 and hashlib.sha256(bytes.fromhex(sha)).digest() for _, _, sha in bindings)
    raw = next(u for u in plan.units if u.treatment_kind == "RAW")
    historical = next(u for u in plan.units if u.treatment_kind == "HISTORICAL_SEED")
    assert raw.treatment_spec_id == "RAW_V1"
    assert historical.treatment_spec_id == "HD_NEXT_1_WINNER_V1"
    assert raw.treatment_spec_sha256 != historical.treatment_spec_sha256
    for unit in plan.units:
        expected = "DIAGNOSTIC_REFERENCE" if unit.model_key == "DEVSTRAL_24B" else "PRIMARY"
        assert unit.model_role == expected
        assert unit.eligible_for_recipe is (expected == "PRIMARY")


def test_a0_replications_are_preregistered_once_with_no_retry_semantics():
    plan = _a0_plan()
    assert all(unit.max_attempts == 1 and unit.retry_of_unit_id is None for unit in plan.units)


def test_a0_freezes_exact_case_set_and_is_order_independent():
    config = load_hd_next2_config(CONFIG)
    canonical = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    forward, = build_stage_plans(StageId.A0, config, canonical, {}, {}, {})
    reverse, = build_stage_plans(StageId.A0, config, reversed(canonical), {}, {}, {})
    assert forward == reverse
    bad_inputs = [
        canonical + [canonical[0]], canonical[:-1],
        [replace(canonical[0], case_id="spoof-20260921-01-001"), *canonical[1:]],
        [replace(canonical[0], metadata={**canonical[0].metadata, "partition": "fresh"}), *canonical[1:]],
        [replace(canonical[0], metadata={**canonical[0].metadata, "hd_next2_region": "TRANSACTION"}), *canonical[1:]],
    ]
    for cases in bad_inputs:
        with pytest.raises(ValueError, match="canonical"):
            build_stage_plans(StageId.A0, config, cases, {}, {}, {})


def test_a0_units_bind_frozen_treatments_and_model_roles():
    plan = _a0_plan()
    expected = {
        "RAW": ("RAW_V1", "4b1cf2ef527726a856f5633419ee3799c7ae144d4d26e8c0c959b6dfa940c422"),
        "HISTORICAL_SEED": ("HD_NEXT_1_WINNER_V1", "74c68acf9532e09536488075d75e0286c6c8404faf9699d831898ce491f8baa8"),
    }
    for unit in plan.units:
        assert (unit.treatment_spec_id, unit.treatment_spec_sha256) == expected[unit.treatment_kind]
        assert (unit.model_role, unit.eligible_for_recipe) == (("DIAGNOSTIC_REFERENCE", False) if unit.model_key == "DEVSTRAL_24B" else ("PRIMARY", True))
    spec = A0_TREATMENT_SPECS["HISTORICAL_SEED"]
    assert dict(spec.information) == {"I1": "ON", "I2": "ON", "I3": "OFF", "I4": "OFF", "I5": "OFF", "I6": "OFF", "I7": "OFF", "I8": "OFF", "I9": "ON", "I10": "ON"}
    assert dict(spec.assistance) == {"A1": "TARGET", "A2": "OFF", "A3": "TARGET", "A4": "OFF"}
    assert tuple(getattr(spec, key) for key in ("amount", "ordering", "representation", "timing", "placement")) == ("MINIMUM", "DEFAULT", "ADMISSIBLE_ACTION_MATRIX", "JUST_IN_TIME", "SYSTEM_CONTEXT")
    with pytest.raises(TypeError):
        spec.information["I1"] = "OFF"
    assert dict(A0_TREATMENT_SPECS["RAW"].information) == {}
    with pytest.raises(TypeError):
        A0_TREATMENT_SPECS["RAW"] = spec


@pytest.mark.parametrize("stage", list(StageId)[1:10])
def test_a1_through_a9_fail_closed_until_a0_evidence_is_analyzed(stage):
    config = load_hd_next2_config(CONFIG)
    with pytest.raises(NotImplementedError, match="deferred until A0/Test-1 evidence is analyzed"):
        build_stage_plans(stage, config, (), {}, {}, {})


def test_a10_is_zero_call_and_deferred():
    config = load_hd_next2_config(CONFIG)
    plan, = build_stage_plans(StageId.A10, config, (), {}, {}, {})
    assert plan.units == ()
    assert plan.forecast_combined_actions == 40
