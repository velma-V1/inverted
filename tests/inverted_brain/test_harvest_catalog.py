from pathlib import Path

import pytest

from inverted_brain.harvest_catalog import load_harvest_catalog


CATALOG = Path("configs/inverted_brain/harvest_sources.yaml")


def test_repository_harvest_catalog_is_valid_and_complete():
    catalog = load_harvest_catalog(CATALOG)
    assert catalog.version == 1
    assert len(catalog.sources) == 19
    assert len(catalog.secondary_sources) == 4
    assert len(catalog.excluded_for_now) == 2
    assert catalog.policy["source_output_is_hypothesis"] is True
    assert catalog.policy["causal_replay_required_for_behavior_promotion"] is True
    assert catalog.policy["fresh_transfer_required_for_behavior_promotion"] is True
    assert catalog.get("comet-mcp").kind == "intelligent_hand"
    assert catalog.get("psychology-of-computer-programming").kind == "book_reference"


def test_catalog_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("""version: 1
policy:
  source_output_is_hypothesis: true
  causal_replay_required_for_behavior_promotion: true
  fresh_transfer_required_for_behavior_promotion: true
sources:
  - {id: x, kind: teacher, target: one}
secondary_sources:
  - {id: x, kind: reference, target: two}
excluded_for_now: []
""", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate source id"):
        load_harvest_catalog(path)


def test_catalog_rejects_missing_target_and_credentialed_url(tmp_path):
    missing = tmp_path / "missing.yaml"
    missing.write_text("""version: 1
policy:
  source_output_is_hypothesis: true
  causal_replay_required_for_behavior_promotion: true
  fresh_transfer_required_for_behavior_promotion: true
sources:
  - {id: x, kind: teacher}
secondary_sources: []
excluded_for_now: []
""", encoding="utf-8")
    with pytest.raises(ValueError, match="target"):
        load_harvest_catalog(missing)

    unsafe = tmp_path / "unsafe.yaml"
    unsafe.write_text("""version: 1
policy:
  source_output_is_hypothesis: true
  causal_replay_required_for_behavior_promotion: true
  fresh_transfer_required_for_behavior_promotion: true
sources:
  - {id: x, kind: teacher, target: one, url: 'https://user:token@example.com/repo'}
secondary_sources: []
excluded_for_now: []
""", encoding="utf-8")
    with pytest.raises(ValueError, match="credentials"):
        load_harvest_catalog(unsafe)
