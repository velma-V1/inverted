from ..adapters.swe_agent import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.TRAJECTORY,
    resume_capability=ResumeCapability.RECONSTRUCTABLE, task_mode_id="trajectory",
)
