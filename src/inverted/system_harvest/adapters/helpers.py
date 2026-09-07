from __future__ import annotations

from .base import (
    AcquisitionAdapter,
    AcquisitionSurface,
    AdapterDescriptor,
    EvidenceOrigin,
    LaunchSpec,
    NativeArtifactSpec,
)
from .sidecar import sidecar_artifacts, sidecar_surfaces


def artifact(artifact_id: str, pattern: str, format: str, *, required: bool = True, description: str = "") -> NativeArtifactSpec:
    return NativeArtifactSpec(artifact_id, pattern, format, True, required, description)


def surface(surface_id: str, channels: tuple[str, ...], artifacts: tuple[str, ...] = (), *,
            phase: str = "STREAM_CAPTURE", origin: EvidenceOrigin = EvidenceOrigin.NATIVE,
            description: str = "", required: bool = True) -> AcquisitionSurface:
    return AcquisitionSurface(surface_id, origin, phase, channels, artifacts, description, required)


def launch(mode_id: str, *argv: str, output_format: str | None = None,
           env_hints: tuple[str, ...] = (), description: str = "") -> LaunchSpec:
    return LaunchSpec(mode_id, tuple(argv), env_hints, output_format, description)

def make_adapter(*, system_id: str, adapter_id: str, execution_modes: tuple[str, ...],
                 native_artifacts: tuple[NativeArtifactSpec, ...],
                 native_surfaces: tuple[AcquisitionSurface, ...],
                 discovery_hints: tuple[str, ...], source_refs: tuple[str, ...],
                 launch_specs: tuple[LaunchSpec, ...]) -> AcquisitionAdapter:
    common_escalation = surface(
        f"{adapter_id}.escalation_capsules", ("ESCALATION_CAPSULES",),
        phase="FAILURE_BOUNDARY", origin=EvidenceOrigin.DERIVED,
        description="Typed failure-boundary escalation capsules from the common harvest layer.",
    )
    descriptor = AdapterDescriptor(
        system_id=system_id,
        adapter_id=adapter_id,
        execution_modes=execution_modes,
        native_artifacts=native_artifacts + sidecar_artifacts(),
        surfaces=native_surfaces + sidecar_surfaces() + (common_escalation,),
        discovery_hints=discovery_hints,
        source_refs=source_refs,
        launch_specs=launch_specs,
    )
    return AcquisitionAdapter(descriptor)
