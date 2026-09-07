from ..adapters.claude_code import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.ONE_SHOT_STRUCTURED,
    resume_capability=ResumeCapability.NATIVE, task_mode_id="stream_json",
)
