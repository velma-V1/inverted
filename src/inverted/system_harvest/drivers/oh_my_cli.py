from ..adapters.oh_my_cli import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.DURABLE_EVIDENCE,
    resume_capability=ResumeCapability.NATIVE, task_mode_id="json",
)
