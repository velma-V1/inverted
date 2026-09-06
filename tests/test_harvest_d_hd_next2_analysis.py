from dataclasses import fields, replace
from pathlib import Path

import pytest

from inverted.harvest_d.hd_next2.analysis import calibrate_noise, summarize_a0
from inverted.harvest_d.hd_next2.cases import OPERATING_REGIONS, generate_hd_next2_cases
from inverted.harvest_d.hd_next2.config import load_hd_next2_config
from inverted.harvest_d.hd_next2.stages import A0Unit, build_stage_plans
from inverted.harvest_d.hd_next2.types import StageId


def _row(model, case, treatment, replicate, correct, answer):
    return {"model_key": model, "case_id": case, "operating_region": "TRANSACTION",
            "treatment_kind": treatment, "replicate": replicate, "correct": correct,
            "normalized_answer": answer, "runtime_seconds": 10.0, "load_seconds": 1.0,
            "prompt_eval_seconds": 2.0, "eval_seconds": 7.0}


def _complete_a0_rows():
    config = load_hd_next2_config(Path("configs/harvest-d-hd-next-2a.json"))
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    plan, = build_stage_plans(StageId.A0, config, cases, {}, {}, {})
    rows = []
    for unit in plan.units:
        row = dict(vars(unit))
        row.update(correct=False, normalized_answer="NO", runtime_seconds=10.0,
                   load_seconds=1.0, prompt_eval_seconds=2.0, eval_seconds=7.0)
        rows.append(row)
    return rows


def test_noise_calibration_uses_worst_complete_four_rep_cell_per_model():
    rows = [_row("SMALL_A", "c1", "RAW", i, True, "A") for i in range(1, 5)]
    rows += [_row("SMALL_A", "c2", "RAW", i, ok, answer) for i, (ok, answer) in enumerate(zip((True, True, False, False), ("A", "A", "B", "C")), 1)]
    result = calibrate_noise(rows)
    assert result.by_model["SMALL_A"].correctness_noise_floor == 0.5
    assert result.by_model["SMALL_A"].answer_noise_floor == 0.5


def test_incomplete_cells_are_ineligible_and_do_not_use_partial_denominators():
    rows = [_row("QWEN", "complete", "RAW", i, True, "A") for i in range(1, 5)]
    rows += [_row("QWEN", "incomplete", "RAW", i, i == 1, str(i)) for i in range(1, 4)]
    result = calibrate_noise(rows)
    incomplete = result.cells[("QWEN", "incomplete", "TRANSACTION", "RAW")]
    assert incomplete.eligible is False
    assert incomplete.correctness_instability == 0.0
    assert incomplete.answer_instability == 0.0
    assert result.by_model["QWEN"].eligible_cell_count == 1


def test_a0_summary_reports_roles_region_pairs_and_strict_ceiling_flags():
    rows = _complete_a0_rows()
    cell = next((r["model_key"], r["case_id"], r["operating_region"]) for r in rows if r["model_key"] == "SMALL_A" and r["treatment_kind"] == "RAW")
    for row in rows:
        if (row["model_key"], row["case_id"], row["operating_region"]) == cell and row["treatment_kind"] == "RAW":
            row["correct"] = True
            row["normalized_answer"] = "YES"
    summary = summarize_a0(rows)
    model = summary.models["SMALL_A"]
    assert (model.model_role, model.eligible_for_recipe) == ("PRIMARY", True)
    assert (summary.models["DEVSTRAL_24B"].model_role, summary.models["DEVSTRAL_24B"].eligible_for_recipe) == ("DIAGNOSTIC_REFERENCE", False)
    assert model.paired_effect.matched_n == 32
    assert set(model.paired_effect_by_region) == set(OPERATING_REGIONS)
    assert model.ceiling_flag is False and model.saturation_flag is False
    assert sum(region.raw_ceiling for region in model.region_flags.values()) == 1
    assert not any(region.historical_ceiling or region.saturated for region in model.region_flags.values())
    assert summary.promoted_recipe is None


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "surplus", "unknown_model", "wrong_region", "wrong_partition", "missing_correct", "invalid_correct", "missing_answer", "empty_answer", "missing_telemetry", "invalid_telemetry", "negative_telemetry", "spoofed_unit"])
def test_a0_summary_fails_closed_on_noncanonical_evidence(mutation):
    rows = _complete_a0_rows()
    if mutation == "missing": rows.pop()
    elif mutation == "duplicate": rows[-1] = dict(rows[0])
    elif mutation == "surplus": rows.append(dict(rows[0], unit_id="surplus"))
    elif mutation == "unknown_model": rows[0]["model_key"] = "OTHER"
    elif mutation == "wrong_region": rows[0]["operating_region"] = "TRANSACTION"
    elif mutation == "wrong_partition": rows[0]["partition"] = "fresh"
    elif mutation == "missing_correct": rows[0].pop("correct")
    elif mutation == "invalid_correct": rows[0]["correct"] = 1
    elif mutation == "missing_answer": rows[0].pop("normalized_answer")
    elif mutation == "empty_answer": rows[0]["normalized_answer"] = ""
    elif mutation == "missing_telemetry": rows[0].pop("eval_seconds")
    elif mutation == "invalid_telemetry": rows[0]["eval_seconds"] = "slow"
    elif mutation == "negative_telemetry": rows[0]["eval_seconds"] = -0.001
    elif mutation == "spoofed_unit": rows[0]["unit_id"] = "spoofed"
    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("treatment_spec_id", "FORGED"),
        ("treatment_spec_sha256", "0" * 64),
        ("execution_position", 999),
        ("model_block", "FORGED-BLOCK"),
        ("model_role", "FORGED-ROLE"),
        ("eligible_for_recipe", False),
        ("max_attempts", 999),
        ("retry_of_unit_id", "FORGED-RETRY"),
    ],
)
def test_a0_summary_rejects_each_forged_canonical_schedule_field(field, forged_value):
    rows = _complete_a0_rows()
    rows[0][field] = forged_value

    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


def test_a0_summary_rejects_substituted_treatment_spec_payload_with_canonical_identity():
    rows = _complete_a0_rows()
    rows[0]["treatment_spec"] = replace(rows[0]["treatment_spec"], amount="FORGED")

    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


def test_a0_summary_rejects_omitted_treatment_spec():
    rows = _complete_a0_rows()
    rows[0].pop("treatment_spec")

    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


def test_a0_summary_rejects_forged_selection_reason():
    rows = _complete_a0_rows()
    rows[0]["selection_reason"] = "forged_selection_reason"

    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


@pytest.mark.parametrize("field", [field.name for field in fields(A0Unit)])
def test_a0_summary_requires_every_canonical_plan_unit_field(field):
    rows = _complete_a0_rows()
    rows[0].pop(field)

    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


@pytest.mark.parametrize("field", [field.name for field in fields(A0Unit)])
def test_a0_summary_rejects_every_forged_canonical_plan_unit_field(field):
    rows = _complete_a0_rows()
    rows[0][field] = object()

    with pytest.raises(ValueError, match="A0 evidence"):
        summarize_a0(rows)


def test_a0_summary_rejects_duplicate_or_missing_treatment_pair():
    rows = _complete_a0_rows()
    raw = next(row for row in rows if row["treatment_kind"] == "RAW")
    index = next(i for i, row in enumerate(rows) if row["model_key"] == raw["model_key"] and row["case_id"] == raw["case_id"] and row["replicate"] == raw["replicate"] and row["treatment_kind"] == "HISTORICAL_SEED")
    rows[index] = dict(raw, unit_id=rows[index]["unit_id"])
    with pytest.raises(ValueError, match="A0 evidence|pair"):
        summarize_a0(rows)
