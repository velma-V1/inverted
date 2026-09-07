from __future__ import annotations

from dataclasses import dataclass

from .aegisevo import ADAPTER as AEGISEVO
from .aider import ADAPTER as AIDER
from .claude_code import ADAPTER as CLAUDE_CODE
from .codex import ADAPTER as CODEX
from .kimi_cli import ADAPTER as KIMI_CLI
from .mini_swe_agent import ADAPTER as MINI_SWE_AGENT
from .oh_my_cli import ADAPTER as OH_MY_CLI
from .openhands import ADAPTER as OPENHANDS
from .pi import ADAPTER as PI
from .prime_agent import ADAPTER as PRIME_AGENT
from .swe_agent import ADAPTER as SWE_AGENT


ADAPTER_IDS = (
    "codex", "claude_code", "prime_agent", "pi", "oh_my_cli",
    "swe_agent", "mini_swe_agent", "aider", "aegisevo", "openhands", "kimi_cli",
)

_ADAPTERS = (
    CODEX, CLAUDE_CODE, PRIME_AGENT, PI, OH_MY_CLI,
    SWE_AGENT, MINI_SWE_AGENT, AIDER, AEGISEVO, OPENHANDS, KIMI_CLI,
)

@dataclass(frozen=True)
class RegistryReport:
    valid: bool
    blockers: tuple[str, ...]
    channel_gaps: dict[str, tuple[str, ...]]


def all_adapters():
    return _ADAPTERS


def adapter_by_id(adapter_id: str):
    for adapter in _ADAPTERS:
        if adapter.descriptor.adapter_id == adapter_id:
            return adapter
    raise KeyError(adapter_id)


def validate_registry(expected_systems: tuple[str, ...], required_channels: tuple[str, ...]) -> RegistryReport:
    blockers: list[str] = []
    systems = tuple(adapter.descriptor.system_id for adapter in _ADAPTERS)
    ids = tuple(adapter.descriptor.adapter_id for adapter in _ADAPTERS)
    if systems != tuple(expected_systems):
        blockers.append("adapter system order does not match frozen campaign")
    if ids != ADAPTER_IDS or len(set(ids)) != len(ids):
        blockers.append("adapter IDs do not match frozen unique registry")
    required = set(required_channels)
    gaps: dict[str, tuple[str, ...]] = {}
    for adapter in _ADAPTERS:
        missing = tuple(sorted(required - set(adapter.descriptor.declared_channels)))
        gaps[adapter.descriptor.adapter_id] = missing
        if missing:
            blockers.append(f"{adapter.descriptor.adapter_id} missing channels: {', '.join(missing)}")
    return RegistryReport(not blockers, tuple(blockers), gaps)


def observability_matrix(required_channels: tuple[str, ...]) -> dict[str, dict[str, tuple[str, ...]]]:
    matrix: dict[str, dict[str, tuple[str, ...]]] = {}
    for channel in required_channels:
        per_adapter: dict[str, tuple[str, ...]] = {}
        for adapter in _ADAPTERS:
            origins = tuple(sorted({
                surface.origin.value
                for surface in adapter.descriptor.surfaces
                if channel in surface.evidence_channels
            }))
            per_adapter[adapter.descriptor.adapter_id] = origins
        matrix[channel] = per_adapter
    return matrix
