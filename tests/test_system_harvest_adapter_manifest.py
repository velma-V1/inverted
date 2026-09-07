from inverted.system_harvest.adapters.manifest import (
    ArtifactManifest,
    capture_artifact_bytes,
    evaluate_artifact_manifest,
)
from inverted.system_harvest.adapters.registry import all_adapters


def test_artifact_capture_records_exact_byte_hash_size_and_paths():
    adapter = all_adapters()[0]
    artifact_id = adapter.descriptor.native_artifacts[0].artifact_id
    raw = b"{\"x\":1}\r\n"
    item = capture_artifact_bytes(
        adapter, artifact_id, raw,
        source_path="source.jsonl", preserved_path="01_RAW/source.jsonl",
    )
    assert item.size_bytes == len(raw)
    assert item.sha256
    assert item.source_path == "source.jsonl"
    assert item.preserved_path == "01_RAW/source.jsonl"
    assert item.planned is True


def test_unplanned_native_artifact_is_preserved_as_discovery_not_dropped():
    adapter = all_adapters()[0]
    item = capture_artifact_bytes(
        adapter, "codex.new_event_dump", b"future-data",
        source_path="new.bin", preserved_path="01_RAW/discovered/new.bin", format="binary",
    )
    assert item.planned is False
    manifest = ArtifactManifest(adapter.descriptor.adapter_id, adapter.descriptor.system_id, "run-1", (item,))
    report = evaluate_artifact_manifest(adapter, manifest)
    assert "codex.new_event_dump" in report.discovered_artifact_ids


def test_missing_required_artifact_blocks_manifest_completion():
    adapter = all_adapters()[1]
    required = next(item for item in adapter.descriptor.native_artifacts if item.required)
    others = []
    for spec in adapter.descriptor.native_artifacts:
        if spec.required and spec.artifact_id != required.artifact_id:
            others.append(capture_artifact_bytes(
                adapter, spec.artifact_id, b"x",
                source_path=spec.artifact_id, preserved_path="01_RAW/" + spec.artifact_id,
            ))
    manifest = ArtifactManifest(adapter.descriptor.adapter_id, adapter.descriptor.system_id, "run-2", tuple(others))
    report = evaluate_artifact_manifest(adapter, manifest)
    assert report.complete is False
    assert any(required.artifact_id in blocker for blocker in report.blockers)


def test_duplicate_planned_artifact_id_blocks_manifest():
    adapter = all_adapters()[2]
    spec = adapter.descriptor.native_artifacts[0]
    item = capture_artifact_bytes(adapter, spec.artifact_id, b"x", source_path="a", preserved_path="01_RAW/a")
    manifest = ArtifactManifest(adapter.descriptor.adapter_id, adapter.descriptor.system_id, "run-3", (item, item))
    report = evaluate_artifact_manifest(adapter, manifest)
    assert report.complete is False
    assert any("duplicate" in blocker for blocker in report.blockers)


def test_multiple_files_under_same_artifact_class_are_allowed():
    adapter = all_adapters()[0]
    items = []
    for spec in adapter.descriptor.native_artifacts:
        if spec.required:
            items.append(capture_artifact_bytes(
                adapter, spec.artifact_id, b"x", source_path=spec.artifact_id + "/a",
                preserved_path="01_RAW/" + spec.artifact_id + "/a",
            ))
    first = next(spec for spec in adapter.descriptor.native_artifacts if spec.required)
    items.append(capture_artifact_bytes(
        adapter, first.artifact_id, b"y", source_path=first.artifact_id + "/b",
        preserved_path="01_RAW/" + first.artifact_id + "/b",
    ))
    report = evaluate_artifact_manifest(
        adapter, ArtifactManifest(adapter.descriptor.adapter_id, adapter.descriptor.system_id, "run-multi", tuple(items))
    )
    assert report.complete is True
