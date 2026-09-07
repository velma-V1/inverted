from ..adapters.openhands import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.ONE_SHOT_STRUCTURED,
    resume_capability=ResumeCapability.NATIVE, task_mode_id="headless_json",
)
