from ..adapters.prime_agent import ADAPTER
from .base import DriverFamily, ResumeCapability, make_driver

DRIVER = make_driver(
    ADAPTER, family=DriverFamily.RPC_SESSION,
    resume_capability=ResumeCapability.NATIVE, task_mode_id="rpc",
)
