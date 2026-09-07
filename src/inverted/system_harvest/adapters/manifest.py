from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .base import AcquisitionAdapter


@dataclass(frozen=True)
class AcquiredArtifact:
    artifact_id: str
    source_path: str
    preserved_path: str
    size_bytes: int
    sha256: str
    format: str
    planned: bool


@dataclass(frozen=True)
class ArtifactManifest:
    adapter_id: str
    system_id: str
    run_id: str
    artifacts: tuple[AcquiredArtifact, ...]


@dataclass(frozen=True)
class ArtifactManifestReport:
    complete: bool
    blockers: tuple[str, ...]
    discovered_artifact_ids: tuple[str, ...]

def capture_artifact_bytes(adapter: AcquisitionAdapter, artifact_id: str, raw: bytes, *,
                           source_path: str, preserved_path: str,
                           format: str | None = None) -> AcquiredArtifact:
    known = {item.artifact_id: item for item in adapter.descriptor.native_artifacts}
    spec = known.get(artifact_id)
    planned = spec is not None
    resolved_format = spec.format if spec is not None else (format or "binary")
    return AcquiredArtifact(
        artifact_id=artifact_id,
        source_path=source_path,
        preserved_path=preserved_path,
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        format=resolved_format,
        planned=planned,
    )


def evaluate_artifact_manifest(adapter: AcquisitionAdapter, manifest: ArtifactManifest) -> ArtifactManifestReport:
    blockers: list[str] = []
    if manifest.adapter_id != adapter.descriptor.adapter_id:
        blockers.append("artifact manifest adapter identity mismatch")
    if manifest.system_id != adapter.descriptor.system_id:
        blockers.append("artifact manifest system identity mismatch")

    keys = [(item.artifact_id, item.source_path, item.preserved_path) for item in manifest.artifacts]
    duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
    if duplicate_keys:
        labels = ["|".join(key) for key in duplicate_keys]
        blockers.append("duplicate artifact records: " + ", ".join(labels))

    present = {item.artifact_id for item in manifest.artifacts}
    for spec in adapter.descriptor.native_artifacts:
        if spec.required and spec.artifact_id not in present:
            blockers.append(f"required artifact missing: {spec.artifact_id}")

    discovered = tuple(sorted({
        item.artifact_id for item in manifest.artifacts if not item.planned
    }))
    return ArtifactManifestReport(not blockers, tuple(blockers), discovered)
