from ..adapters.aegisevo import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.EVIDENCE_CONTROL_PLANE,
    resume_capability=ResumeCapability.RECONSTRUCTABLE,
    task_mode_id="deterministic_fixture", live_mode_id="live_harness",
    live_requires_instrumentation=True,
)
