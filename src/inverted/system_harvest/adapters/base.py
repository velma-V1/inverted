from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..evidence import content_hash


class EvidenceOrigin(str, Enum):
    NATIVE = "NATIVE"
    SIDECAR = "SIDECAR"
    DERIVED = "DERIVED"
    INSTRUMENTED = "INSTRUMENTED"
    INACCESSIBLE = "INACCESSIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class NativeArtifactSpec:
    artifact_id: str
    pattern: str
    format: str
    lossless: bool
    required: bool
    description: str = ""

@dataclass(frozen=True)
class AcquisitionSurface:
    surface_id: str
    origin: EvidenceOrigin
    phase: str
    evidence_channels: tuple[str, ...]
    native_artifact_ids: tuple[str, ...] = ()
    description: str = ""
    required: bool = True


@dataclass(frozen=True)
class LaunchSpec:
    mode_id: str
    argv: tuple[str, ...]
    env_hints: tuple[str, ...] = ()
    output_format: str | None = None
    description: str = ""


@dataclass(frozen=True)
class CapturedNativeRecord:
    payload: Any
    source_path: str
    ordinal: int
    origin: EvidenceOrigin
    content_sha256: str
    raw_text: str | None = None
    raw_sha256: str | None = None
    parse_error: str | None = None

@dataclass(frozen=True)
class AcquisitionPlan:
    system_id: str
    adapter_id: str
    workspace: str
    run_dir: str
    task_id: str
    launch_specs: tuple[LaunchSpec, ...]
    surfaces: tuple[AcquisitionSurface, ...]
    native_artifacts: tuple[NativeArtifactSpec, ...]


@dataclass(frozen=True)
class AdapterDescriptor:
    system_id: str
    adapter_id: str
    execution_modes: tuple[str, ...]
    native_artifacts: tuple[NativeArtifactSpec, ...]
    surfaces: tuple[AcquisitionSurface, ...]
    discovery_hints: tuple[str, ...]
    source_refs: tuple[str, ...]
    launch_specs: tuple[LaunchSpec, ...] = ()

    def __post_init__(self) -> None:
        artifact_ids = [item.artifact_id for item in self.native_artifacts]
        surface_ids = [item.surface_id for item in self.surfaces]
        if len(artifact_ids) != len(set(artifact_ids)) or len(surface_ids) != len(set(surface_ids)):
            raise ValueError("duplicate adapter artifact or surface id")

        known = set(artifact_ids)
        for surface in self.surfaces:
            unknown = set(surface.native_artifact_ids) - known
            if unknown:
                raise ValueError(f"surface {surface.surface_id} references unknown artifact(s): {sorted(unknown)}")

    @property
    def declared_channels(self) -> tuple[str, ...]:
        channels = {channel for surface in self.surfaces for channel in surface.evidence_channels}
        return tuple(sorted(channels))


class AcquisitionAdapter:
    def __init__(self, descriptor: AdapterDescriptor):
        self.descriptor = descriptor

    def build_acquisition_plan(self, workspace: str, run_dir: str, task_id: str) -> AcquisitionPlan:
        return AcquisitionPlan(
            system_id=self.descriptor.system_id,
            adapter_id=self.descriptor.adapter_id,
            workspace=str(workspace), run_dir=str(run_dir), task_id=str(task_id),
            launch_specs=self.descriptor.launch_specs,
            surfaces=self.descriptor.surfaces,
            native_artifacts=self.descriptor.native_artifacts,
        )

    def ingest_native_record(self, payload: Any, *, source_path: str, ordinal: int) -> CapturedNativeRecord:
        if ordinal < 0:
            raise ValueError("ordinal must be non-negative")
        return CapturedNativeRecord(payload, source_path, ordinal, EvidenceOrigin.NATIVE, content_hash(payload))

    def ingest_native_text(self, raw_text: str, *, source_path: str, ordinal: int,
                           format: str) -> CapturedNativeRecord:
        if ordinal < 0:
            raise ValueError("ordinal must be non-negative")
        raw_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        payload: Any = raw_text
        parse_error: str | None = None
        if format.lower() in {"json", "jsonl"}:
            try:
                payload = json.loads(raw_text.rstrip("\r\n"))
            except json.JSONDecodeError as exc:
                parse_error = f"{exc.__class__.__name__}: {exc}"
        return CapturedNativeRecord(
            payload=payload,
            source_path=source_path,
            ordinal=ordinal,
            origin=EvidenceOrigin.NATIVE,
            content_sha256=content_hash(payload),
            raw_text=raw_text,
            raw_sha256=raw_sha256,
            parse_error=parse_error,
        )
