from inverted.system_harvest.adapters.base import EvidenceOrigin
from inverted.system_harvest.adapters.sidecar import SIDECAR_CHANNELS, sidecar_artifacts, sidecar_surfaces


def test_sidecar_declares_required_passive_state_channels():
    expected = {
        "PROCESS_IO", "FILESYSTEM_DIFFS", "STATE_TRANSITIONS",
        "RUNTIME_TELEMETRY", "SOURCE_PROVENANCE",
    }
    assert expected.issubset(SIDECAR_CHANNELS)
    assert all(surface.origin is EvidenceOrigin.SIDECAR for surface in sidecar_surfaces())


def test_sidecar_preserves_git_fs_process_env_and_resource_artifacts():
    ids = {artifact.artifact_id for artifact in sidecar_artifacts()}
    assert {
        "sidecar.stdout_stderr", "sidecar.fs_before", "sidecar.fs_after",
        "sidecar.git_before", "sidecar.git_after", "sidecar.process_tree",
        "sidecar.environment", "sidecar.resources",
    }.issubset(ids)
    assert all(artifact.lossless for artifact in sidecar_artifacts())


def test_environment_artifact_requires_redaction_metadata():
    environment = next(item for item in sidecar_artifacts() if item.artifact_id == "sidecar.environment")
    assert "redact" in environment.description.lower()
    assert "fingerprint" in environment.description.lower()
