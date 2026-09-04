from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path


def _load_module():
    name = "inverted.harvest_d.d3_closure_prior_evidence"
    spec = importlib.util.find_spec(name)
    assert spec is not None, "R0 prior-evidence module is missing"
    return importlib.import_module(name)


def test_small_historical_dataset_is_preserved_as_prior_not_fresh_confirmation(tmp_path: Path):
    module = _load_module()
    case_dir = tmp_path / "cases" / "harvest_d"
    case_dir.mkdir(parents=True)
    source = case_dir / "d2-qwen-gain-v1.jsonl"
    source.write_text("\n".join(json.dumps({"case_id": f"c{i}", "family": "EVIDENCE"}) for i in range(3)) + "\n")

    records = module.inventory_prior_evidence(tmp_path)
    record = next(row for row in records if row.source_path == "cases/harvest_d/d2-qwen-gain-v1.jsonl")

    assert record.present is True
    assert record.sample_size == 3
    assert record.evidence_tier is module.EvidenceTier.HISTORICAL_PRIOR
    assert record.causal_strength in {
        module.PriorValueClass.STRONG_CAUSAL_PRIOR,
        module.PriorValueClass.USEFUL_DIRECTIONAL_PRIOR,
        module.PriorValueClass.FAILURE_ATLAS_PRIOR,
    }
    assert "scheduler_prior" in record.reusable_for
    assert "fresh_confirmation" in record.forbidden_for
    assert "sealed_confirmation" in record.forbidden_for
    assert "global_optimum" in record.forbidden_for
    assert 0.0 < record.scheduler_prior_weight <= 1.0


def test_missing_expected_prior_is_preserved_as_bounded_unavailable_record(tmp_path: Path):
    module = _load_module()
    records = module.inventory_prior_evidence(tmp_path)
    record = next(row for row in records if row.evidence_source_id == "D2_QWEN_GAIN_V1")

    assert record.present is False
    assert record.sample_size == 0
    assert record.evidence_tier is module.EvidenceTier.HISTORICAL_PRIOR
    assert record.scheduler_prior_weight == 0.0
    assert "missing" in record.reason.lower() or "unavailable" in record.reason.lower()


def test_prior_weight_is_metadata_not_a_fresh_observation_count(tmp_path: Path):
    module = _load_module()
    case_dir = tmp_path / "cases" / "harvest_d"
    case_dir.mkdir(parents=True)
    (case_dir / "d2-qwen-gain-v1.jsonl").write_text(json.dumps({"case_id": "only"}) + "\n")

    record = next(row for row in module.inventory_prior_evidence(tmp_path) if row.evidence_source_id == "D2_QWEN_GAIN_V1")

    payload = record.to_dict()
    assert "effective_fresh_n" not in payload
    assert payload["sample_size"] == 1
    assert payload["evidence_tier"] == "E1_HISTORICAL_PRIOR"
    assert payload["scheduler_prior_weight"] > 0.0


def test_prior_inventory_is_deterministic_for_same_repository_state(tmp_path: Path):
    module = _load_module()
    case_dir = tmp_path / "cases" / "harvest_d"
    case_dir.mkdir(parents=True)
    (case_dir / "d2-small-a-seed-v1.jsonl").write_text(
        json.dumps({"case_id": "a", "family": "STATE"}) + "\n" +
        json.dumps({"case_id": "b", "family": "AUTHORITY"}) + "\n"
    )

    first = [row.to_dict() for row in module.inventory_prior_evidence(tmp_path)]
    second = [row.to_dict() for row in module.inventory_prior_evidence(tmp_path)]

    assert first == second
