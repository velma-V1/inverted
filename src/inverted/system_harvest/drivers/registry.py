from __future__ import annotations

from dataclasses import dataclass

from ..adapters.registry import ADAPTER_IDS
from .aegisevo import DRIVER as AEGISEVO
from .aider import DRIVER as AIDER
from .claude_code import DRIVER as CLAUDE_CODE
from .codex import DRIVER as CODEX
from .kimi_cli import DRIVER as KIMI_CLI
from .mini_swe_agent import DRIVER as MINI_SWE_AGENT
from .oh_my_cli import DRIVER as OH_MY_CLI
from .openhands import DRIVER as OPENHANDS
from .pi import DRIVER as PI
from .prime_agent import DRIVER as PRIME_AGENT
from .swe_agent import DRIVER as SWE_AGENT


_DRIVERS = (
    CODEX, CLAUDE_CODE, PRIME_AGENT, PI, OH_MY_CLI,
    SWE_AGENT, MINI_SWE_AGENT, AIDER, AEGISEVO, OPENHANDS, KIMI_CLI,
)


@dataclass(frozen=True)
class DriverRegistryReport:
    valid: bool
    blockers: tuple[str, ...]


def all_drivers():
    return _DRIVERS


def driver_by_adapter_id(adapter_id: str):
    for driver in _DRIVERS:
        if driver.descriptor.adapter_id == adapter_id:
            return driver
    raise KeyError(adapter_id)


def validate_driver_registry(adapters, drivers) -> DriverRegistryReport:
    adapters = tuple(adapters)
    drivers = tuple(drivers)
    blockers: list[str] = []
    ids = tuple(driver.descriptor.adapter_id for driver in drivers)
    if ids != ADAPTER_IDS or len(set(ids)) != len(ids):
        blockers.append("driver IDs do not match frozen adapter registry")
    adapter_by_id = {adapter.descriptor.adapter_id: adapter for adapter in adapters}
    for driver in drivers:
        descriptor = driver.descriptor
        adapter = adapter_by_id.get(descriptor.adapter_id)
        if adapter is None:
            blockers.append(f"driver has no adapter: {descriptor.adapter_id}")
            continue
        if descriptor.system_id != adapter.descriptor.system_id:
            blockers.append(f"driver system mismatch: {descriptor.adapter_id}")
        if descriptor.task_mode_id not in adapter.descriptor.execution_modes:
            blockers.append(f"driver mode unavailable: {descriptor.adapter_id}/{descriptor.task_mode_id}")
        if not descriptor.artifact_watch_patterns:
            blockers.append(f"driver artifact watch contract missing: {descriptor.adapter_id}")
        if descriptor.shell_fallback:
            blockers.append(f"generic shell fallback forbidden: {descriptor.adapter_id}")
    return DriverRegistryReport(not blockers, tuple(blockers))
