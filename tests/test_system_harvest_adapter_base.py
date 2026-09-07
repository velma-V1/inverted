from dataclasses import FrozenInstanceError

import pytest

from inverted.system_harvest.adapters.base import (
    AcquisitionAdapter,
    AcquisitionSurface,
    AdapterDescriptor,
    EvidenceOrigin,
    NativeArtifactSpec,
)


def _adapter():
    descriptor = AdapterDescriptor(
        system_id="Example", adapter_id="example", execution_modes=("jsonl",),
        native_artifacts=(NativeArtifactSpec("session", "*.jsonl", "jsonl", True, True),),
        surfaces=(AcquisitionSurface("events", EvidenceOrigin.NATIVE, "STREAM_CAPTURE", ("MODEL_IO",), ("session",)),),
        discovery_hints=("example --version",), source_refs=("https://example.invalid/docs",),
    )
    return AcquisitionAdapter(descriptor)


def test_descriptor_is_immutable_and_native_artifact_is_lossless():
    adapter = _adapter()
    assert adapter.descriptor.native_artifacts[0].lossless is True
    with pytest.raises(FrozenInstanceError):
        adapter.descriptor.system_id = "changed"

def test_plan_is_declarative_and_keeps_native_surfaces():
    adapter = _adapter()
    plan = adapter.build_acquisition_plan("C:/work", "C:/run", "task-1")
    assert plan.system_id == "Example"
    assert plan.workspace == "C:/work"
    assert plan.launch_specs == ()
    assert plan.surfaces == adapter.descriptor.surfaces


def test_native_ingest_preserves_arbitrary_payload_identity_and_lineage():
    adapter = _adapter()
    payload = {"type": "event", "nested": {"x": [1, 2]}, "text": "raw\nvalue"}
    record = adapter.ingest_native_record(payload, source_path="session.jsonl", ordinal=7)
    assert record.payload == payload
    assert record.source_path == "session.jsonl"
    assert record.ordinal == 7
    assert record.origin is EvidenceOrigin.NATIVE
    assert record.content_sha256


def test_descriptor_rejects_duplicate_surface_or_artifact_ids():
    with pytest.raises(ValueError, match="duplicate"):
        AdapterDescriptor(
            system_id="X", adapter_id="x", execution_modes=("jsonl",),
            native_artifacts=(NativeArtifactSpec("a", "*.json", "json", True, True), NativeArtifactSpec("a", "*.log", "text", True, False)),
            surfaces=(), discovery_hints=("x --version",), source_refs=("ref",),
        )

def test_native_text_ingest_preserves_exact_wire_record_and_decoded_payload():
    adapter = _adapter()
    raw = '{"b":2, "a":1, "text":"x\\n"}\r\n'
    record = adapter.ingest_native_text(raw, source_path="wire.jsonl", ordinal=3, format="jsonl")
    assert record.raw_text == raw
    assert record.raw_sha256
    assert record.payload == {"b": 2, "a": 1, "text": "x\n"}
    assert record.content_sha256


def test_native_text_ingest_keeps_non_json_text_verbatim():
    adapter = _adapter()
    raw = "stderr line 1\r\nstderr line 2\n"
    record = adapter.ingest_native_text(raw, source_path="stderr.log", ordinal=1, format="text")
    assert record.payload == raw
    assert record.raw_text == raw
