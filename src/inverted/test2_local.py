"""Public interface for the bounded Test-2 local campaign.

The implementation is isolated in ``test2_local_impl`` so the experiment
surface stays small and import-stable while the campaign logic remains
independently testable.
"""

from .test2_local_impl import (
    BoundedCompletion,
    BoundedModelCaller,
    LOCAL_MODELS,
    LOCAL_PHASE_LIMITS,
    PROGRESSIVE_PIPELINES,
    LocalTest2Plan,
    build_local_plan,
    build_progressive_role_assignments,
    run_local_campaign,
)

__all__ = [
    "BoundedCompletion",
    "BoundedModelCaller",
    "LOCAL_MODELS",
    "LOCAL_PHASE_LIMITS",
    "PROGRESSIVE_PIPELINES",
    "LocalTest2Plan",
    "build_local_plan",
    "build_progressive_role_assignments",
    "run_local_campaign",
]
