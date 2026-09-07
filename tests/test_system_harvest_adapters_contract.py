from pathlib import Path

from inverted.system_harvest import load_harvest_template
from inverted.system_harvest.adapters import ADAPTER_IDS, all_adapters, validate_registry


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = load_harvest_template(ROOT / "configs" / "system-harvest-11" / "campaign.json")


def test_all_eleven_plans_include_sidecar_and_escalation_capture():
    for adapter in all_adapters():
        plan = adapter.build_acquisition_plan("C:/work", "C:/run", "task")
        surface_ids = {surface.surface_id for surface in plan.surfaces}
        assert "sidecar.process_io" in surface_ids
        assert "sidecar.filesystem" in surface_ids
        assert f"{adapter.descriptor.adapter_id}.escalation_capsules" in surface_ids
        artifact_ids = {artifact.artifact_id for artifact in plan.native_artifacts}
        assert "sidecar.environment" in artifact_ids
        assert "sidecar.resources" in artifact_ids


def test_all_eleven_losslessly_ingest_native_wire_fixture():
    raw = '{"type":"event","seq":4,"payload":{"x":1}}\r\n'
    for adapter in all_adapters():
        record = adapter.ingest_native_text(raw, source_path="native.jsonl", ordinal=4, format="jsonl")
        assert record.raw_text == raw
        assert record.payload["seq"] == 4
        assert record.raw_sha256 and record.content_sha256


def test_registry_is_complete_against_campaign_channels():
    report = validate_registry(TEMPLATE.systems, TEMPLATE.required_evidence_channels)
    assert report.valid is True
    assert tuple(adapter.descriptor.adapter_id for adapter in all_adapters()) == ADAPTER_IDS


def test_adapter_modules_do_not_import_execution_or_network_clients():
    adapter_dir = ROOT / "src" / "inverted" / "system_harvest" / "adapters"
    forbidden = ("subprocess", "requests", "httpx", "socket", "urllib", "openai", "anthropic")
    for path in adapter_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert f"import {token}" not in text
            assert f"from {token}" not in text


def test_no_adapter_uses_placeholder_provenance_or_empty_native_description():
    for adapter in all_adapters():
        descriptor = adapter.descriptor
        assert all("example.invalid" not in ref for ref in descriptor.source_refs)
        native = [surface for surface in descriptor.surfaces if surface.surface_id.startswith(descriptor.adapter_id.split('_')[0])]
        assert native
        assert all(surface.description for surface in native)
