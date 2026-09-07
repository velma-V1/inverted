from pathlib import Path

from inverted.system_harvest import load_harvest_template
from inverted.system_harvest.adapters.registry import ADAPTER_IDS, all_adapters, validate_registry


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = load_harvest_template(ROOT / "configs" / "system-harvest-11" / "campaign.json")
EXPECTED_IDS = (
    "codex", "claude_code", "prime_agent", "pi", "oh_my_cli",
    "swe_agent", "mini_swe_agent", "aider", "aegisevo", "openhands", "kimi_cli",
)


def test_registry_exactly_matches_frozen_system_order_and_adapter_ids():
    adapters = all_adapters()
    assert tuple(item.descriptor.system_id for item in adapters) == TEMPLATE.systems
    assert ADAPTER_IDS == EXPECTED_IDS
    assert tuple(item.descriptor.adapter_id for item in adapters) == EXPECTED_IDS
    assert len({id(item) for item in adapters}) == 11


def test_every_adapter_declares_real_native_sources_and_discovery_hints():
    for adapter in all_adapters():
        descriptor = adapter.descriptor
        assert descriptor.source_refs
        assert descriptor.discovery_hints
        assert descriptor.surfaces
        assert descriptor.native_artifacts


def test_registry_covers_every_mandatory_evidence_channel_with_declared_origin():
    report = validate_registry(TEMPLATE.systems, TEMPLATE.required_evidence_channels)
    assert report.valid is True
    assert report.blockers == ()
    for adapter_id in EXPECTED_IDS:
        assert report.channel_gaps[adapter_id] == ()


def test_every_adapter_builds_declarative_plan_without_execution():
    for adapter in all_adapters():
        plan = adapter.build_acquisition_plan("C:/fixture-work", "C:/fixture-run", "task-1")
        assert plan.adapter_id == adapter.descriptor.adapter_id
        assert plan.system_id == adapter.descriptor.system_id
        assert plan.surfaces
        assert plan.native_artifacts


def test_observability_matrix_preserves_origin_per_system_channel():
    from inverted.system_harvest.adapters.registry import observability_matrix

    matrix = observability_matrix(TEMPLATE.required_evidence_channels)
    assert set(matrix) == set(TEMPLATE.required_evidence_channels)
    assert set(matrix["MODEL_IO"]) == set(EXPECTED_IDS)
    assert "NATIVE" in matrix["MODEL_IO"]["codex"]
    assert "INSTRUMENTED" in matrix["MODEL_IO"]["aegisevo"]
    assert "SIDECAR" in matrix["PROCESS_IO"]["codex"]
    assert "DERIVED" in matrix["ESCALATION_CAPSULES"]["kimi_cli"]
