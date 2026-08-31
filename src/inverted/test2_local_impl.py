"""Compatibility surface for the contamination-hardened Test-2 local runner.

The implementation lives in ``test2_local_hardened``. Keeping this module as a
thin re-export preserves the public/import contract used by existing tests and
callers while making the scientific hardening changes independently auditable.
"""

from .test2_local_hardened import *  # noqa: F401,F403
from .test2_local_hardened import LOCAL_PHASE_LIMITS, LocalTest2Plan


def build_local_plan() -> LocalTest2Plan:
    """Report the preregistered 480-call ceiling/reservation.

    The current execution graph normally uses fewer physical calls through
    selective auditing/caching, but the dry plan must describe the fixed
    maximum rather than an optimistic realized estimate.
    """
    total = sum(LOCAL_PHASE_LIMITS.values())
    if total != 480:
        raise AssertionError(f"local Test-2 phase reservations must sum to 480, got {total}")
    return LocalTest2Plan(planned_max_physical_calls=480)
