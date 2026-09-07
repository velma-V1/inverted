from __future__ import annotations

from .base import AcquisitionSurface, EvidenceOrigin, NativeArtifactSpec


SIDECAR_CHANNELS = frozenset({
    "PROCESS_IO",
    "FILESYSTEM_DIFFS",
    "STATE_TRANSITIONS",
    "RUNTIME_TELEMETRY",
    "SOURCE_PROVENANCE",
})


def sidecar_artifacts() -> tuple[NativeArtifactSpec, ...]:
    return (
        NativeArtifactSpec("sidecar.stdout_stderr", "sidecar/stdout-stderr.jsonl", "jsonl", True, True),
        NativeArtifactSpec("sidecar.fs_before", "sidecar/fs-before.json", "json", True, True),
        NativeArtifactSpec("sidecar.fs_after", "sidecar/fs-after.json", "json", True, True),
        NativeArtifactSpec("sidecar.git_before", "sidecar/git-before.json", "json", True, True),
        NativeArtifactSpec("sidecar.git_after", "sidecar/git-after.json", "json", True, True),
        NativeArtifactSpec("sidecar.process_tree", "sidecar/process-tree.jsonl", "jsonl", True, True),
        NativeArtifactSpec(
            "sidecar.environment", "sidecar/environment.json", "json", True, True,
            "Environment names plus redacted values and stable fingerprints; never plaintext secrets.",
        ),
        NativeArtifactSpec("sidecar.resources", "sidecar/resources.jsonl", "jsonl", True, True),
    )

def sidecar_surfaces() -> tuple[AcquisitionSurface, ...]:
    return (
        AcquisitionSurface(
            "sidecar.process_io", EvidenceOrigin.SIDECAR, "STREAM_CAPTURE",
            ("PROCESS_IO",), ("sidecar.stdout_stderr", "sidecar.process_tree"),
            "Process tree plus stdout/stderr capture.",
        ),
        AcquisitionSurface(
            "sidecar.filesystem", EvidenceOrigin.SIDECAR, "SNAPSHOT_BEFORE_AFTER",
            ("FILESYSTEM_DIFFS", "STATE_TRANSITIONS"),
            ("sidecar.fs_before", "sidecar.fs_after"), "Filesystem manifests and deltas.",
        ),
        AcquisitionSurface(
            "sidecar.git", EvidenceOrigin.SIDECAR, "SNAPSHOT_BEFORE_AFTER",
            ("SOURCE_PROVENANCE", "STATE_TRANSITIONS"),
            ("sidecar.git_before", "sidecar.git_after"), "Git identity, status and diffs.",
        ),
        AcquisitionSurface(
            "sidecar.environment", EvidenceOrigin.SIDECAR, "SNAPSHOT_BEFORE",
            ("SOURCE_PROVENANCE",), ("sidecar.environment",),
            "Redacted environment/config provenance.",
        ),
        AcquisitionSurface(
            "sidecar.resources", EvidenceOrigin.SIDECAR, "STREAM_CAPTURE",
            ("RUNTIME_TELEMETRY",), ("sidecar.resources",), "Resource samples and timing.",
        ),
    )
