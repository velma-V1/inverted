from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..adapters.base import AcquisitionAdapter, LaunchSpec


class DriverFamily(str, Enum):
    ONE_SHOT_STRUCTURED = "ONE_SHOT_STRUCTURED"
    RPC_SESSION = "RPC_SESSION"
    TRAJECTORY = "TRAJECTORY"
    HISTORY_EDIT = "HISTORY_EDIT"
    EVIDENCE_CONTROL_PLANE = "EVIDENCE_CONTROL_PLANE"
    DURABLE_EVIDENCE = "DURABLE_EVIDENCE"


class ResumeCapability(str, Enum):
    NATIVE = "NATIVE"
    RECONSTRUCTABLE = "RECONSTRUCTABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ExecutionDriverDescriptor:
    system_id: str
    adapter_id: str
    family: DriverFamily
    resume_capability: ResumeCapability
    task_mode_id: str
    artifact_watch_patterns: tuple[tuple[str, str], ...]
    live_mode_id: str | None = None
    live_requires_instrumentation: bool = False
    shell_fallback: bool = False


class ExecutionDriver:
    def __init__(self, descriptor: ExecutionDriverDescriptor):
        self.descriptor = descriptor

    def declared_launch_spec(self, adapter: AcquisitionAdapter) -> LaunchSpec:
        for spec in adapter.descriptor.launch_specs:
            if spec.mode_id == self.descriptor.task_mode_id:
                return spec
        raise RuntimeError(
            f"driver {self.descriptor.adapter_id} has no adapter launch spec for {self.descriptor.task_mode_id}"
        )


def make_driver(adapter: AcquisitionAdapter, *, family: DriverFamily,
                resume_capability: ResumeCapability, task_mode_id: str,
                live_mode_id: str | None = None,
                live_requires_instrumentation: bool = False) -> ExecutionDriver:
    if task_mode_id not in adapter.descriptor.execution_modes:
        raise ValueError(f"unknown driver task mode: {task_mode_id}")
    patterns = tuple((item.artifact_id, item.pattern) for item in adapter.descriptor.native_artifacts)
    descriptor = ExecutionDriverDescriptor(
        system_id=adapter.descriptor.system_id,
        adapter_id=adapter.descriptor.adapter_id,
        family=family,
        resume_capability=resume_capability,
        task_mode_id=task_mode_id,
        artifact_watch_patterns=patterns,
        live_mode_id=live_mode_id,
        live_requires_instrumentation=live_requires_instrumentation,
        shell_fallback=False,
    )
    return ExecutionDriver(descriptor)
