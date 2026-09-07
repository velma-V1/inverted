from __future__ import annotations

from dataclasses import dataclass

from .base import AcquisitionAdapter


@dataclass(frozen=True)
class PreflightObservation:
    adapter_id: str
    version: str
    source_revision: str
    supported_modes: tuple[str, ...]
    captureable_artifact_ids: tuple[str, ...]
    captureable_surface_ids: tuple[str, ...]


@dataclass(frozen=True)
class PreflightReport:
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def evaluate_preflight(adapter: AcquisitionAdapter, observation: PreflightObservation) -> PreflightReport:
    descriptor = adapter.descriptor
    blockers: list[str] = []
    warnings: list[str] = []
    if observation.adapter_id != descriptor.adapter_id:
        blockers.append("adapter identity mismatch")
    if not observation.version.strip():
        blockers.append("target version missing")
    if not observation.source_revision.strip():
        blockers.append("source revision missing")

    if not set(observation.supported_modes).intersection(descriptor.execution_modes):
        blockers.append("no supported execution mode available")

    captureable_artifacts = set(observation.captureable_artifact_ids)
    for artifact in descriptor.native_artifacts:
        if artifact.required and artifact.artifact_id not in captureable_artifacts:
            blockers.append(f"required artifact not captureable: {artifact.artifact_id}")

    captureable_surfaces = set(observation.captureable_surface_ids)
    for surface in descriptor.surfaces:
        if surface.required and surface.surface_id not in captureable_surfaces:
            blockers.append(f"required surface not captureable: {surface.surface_id}")

    optional_missing = [
        artifact.artifact_id for artifact in descriptor.native_artifacts
        if not artifact.required and artifact.artifact_id not in captureable_artifacts
    ]
    if optional_missing:
        warnings.append("optional artifacts unavailable: " + ", ".join(optional_missing))

    return PreflightReport(not blockers, tuple(blockers), tuple(warnings))
