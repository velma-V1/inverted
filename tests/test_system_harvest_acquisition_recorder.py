from pathlib import Path

import pytest

from inverted.system_harvest.acquisition import AcquisitionRecorder
from inverted.system_harvest.adapters.preflight import PreflightObservation, evaluate_preflight
from inverted.system_harvest.adapters.registry import all_adapters
from inverted.system_harvest.journal import HarvestJournal


def _ready(adapter):
    d = adapter.descriptor
    obs = PreflightObservation(
        d.adapter_id, "1.0", "commit-abc", d.execution_modes,
        tuple(a.artifact_id for a in d.native_artifacts),
        tuple(s.surface_id for s in d.surfaces),
    )
    return evaluate_preflight(adapter, obs)


def test_recorder_refuses_to_start_when_preflight_is_not_ready(tmp_path):
    adapter = all_adapters()[0]
    bad = evaluate_preflight(adapter, PreflightObservation(adapter.descriptor.adapter_id, "", "", (), (), ()))
    with pytest.raises(ValueError, match="preflight"):
        AcquisitionRecorder("C", "run-1", "task-1", adapter, tmp_path, bad)


def test_recorder_preserves_exact_stream_text_and_journals_hashes(tmp_path):
    adapter = all_adapters()[0]
    recorder = AcquisitionRecorder("C", "run-1", "task-1", adapter, tmp_path, _ready(adapter))
    raw = '{"type":"event","x":1}\r\n'
    record = recorder.record_native_text("codex.exec_jsonl", raw, source_path="stdout", ordinal=1, format="jsonl")
    assert record.raw_text == raw
    stream_path = recorder.stream_path("codex.exec_jsonl")
    assert stream_path.read_bytes() == raw.encode("utf-8")
    journal = HarvestJournal(tmp_path / "journal.jsonl", "C").read_all()
    assert journal[-1].kind == "NATIVE_STREAM_RECORD"
    assert journal[-1].payload["raw_sha256"] == record.raw_sha256

def test_recorder_preserves_malformed_json_wire_text_instead_of_rejecting_it(tmp_path):
    adapter = all_adapters()[0]
    recorder = AcquisitionRecorder("C", "run-bad-json", "task", adapter, tmp_path, _ready(adapter))
    raw = '{"type":"event","broken":}\n'
    record = recorder.record_native_text("codex.exec_jsonl", raw, source_path="stdout", ordinal=2, format="jsonl")
    assert record.raw_text == raw
    assert record.payload == raw
    assert record.parse_error
    assert recorder.stream_path("codex.exec_jsonl").read_bytes() == raw.encode("utf-8")


def test_record_artifact_bytes_preserves_exact_bytes_and_discovered_artifacts(tmp_path):
    adapter = all_adapters()[0]
    recorder = AcquisitionRecorder("C", "run-artifact", "task", adapter, tmp_path, _ready(adapter))
    planned = recorder.record_artifact_bytes("codex.session", b"\x00session\xff", source_path="session/state.bin")
    discovered = recorder.record_artifact_bytes("codex.future_trace", b"future", source_path="future.trace", format="binary")
    assert Path(planned.preserved_path).read_bytes() == b"\x00session\xff"
    assert Path(discovered.preserved_path).read_bytes() == b"future"
    assert planned.planned is True
    assert discovered.planned is False

def test_finalize_manifest_includes_streams_and_reports_unplanned_discoveries(tmp_path):
    adapter = all_adapters()[0]
    recorder = AcquisitionRecorder("C", "run-final", "task", adapter, tmp_path, _ready(adapter))
    for spec in adapter.descriptor.native_artifacts:
        if spec.required and spec.artifact_id != "codex.exec_jsonl":
            recorder.record_artifact_bytes(spec.artifact_id, b"fixture", source_path=spec.artifact_id)
    recorder.record_native_text("codex.exec_jsonl", '{"ok":true}\n', source_path="stdout", ordinal=1, format="jsonl")
    recorder.record_artifact_bytes("codex.unknown_dump", b"new", source_path="new.dump", format="binary")
    manifest, report = recorder.finalize_manifest()
    assert report.complete is True
    assert "codex.unknown_dump" in report.discovered_artifact_ids
    assert any(item.artifact_id == "codex.exec_jsonl" for item in manifest.artifacts)


def test_every_adapter_can_generate_complete_fixture_manifest_without_live_execution(tmp_path):
    for index, adapter in enumerate(all_adapters()):
        run_dir = tmp_path / f"run-{index}"
        recorder = AcquisitionRecorder("C", f"run-{index}", "task", adapter, run_dir, _ready(adapter))
        for spec in adapter.descriptor.native_artifacts:
            if spec.required:
                recorder.record_artifact_bytes(spec.artifact_id, b"fixture", source_path=spec.artifact_id)
        _, report = recorder.finalize_manifest()
        assert report.complete is True, (adapter.descriptor.adapter_id, report.blockers)
