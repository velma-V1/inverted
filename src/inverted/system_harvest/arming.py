from __future__ import annotations

from enum import Enum


class ArmState(str, Enum):
    BUILD = "BUILD"
    DRY_RUN = "DRY_RUN"
    PREFLIGHT_PROBE = "PREFLIGHT_PROBE"
    ARMED_LIVE = "ARMED_LIVE"

    @property
    def task_execution_allowed(self) -> bool:
        return self is ArmState.ARMED_LIVE

    @property
    def probe_execution_allowed(self) -> bool:
        return self in {ArmState.PREFLIGHT_PROBE, ArmState.ARMED_LIVE}


ALLOWED_PREFLIGHT_PROBES = frozenset({"version", "help", "identity"})
