from ..adapters.aider import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.HISTORY_EDIT,
    resume_capability=ResumeCapability.RECONSTRUCTABLE, task_mode_id="message",
)
