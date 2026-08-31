"""Compatibility surface for the contamination-hardened Test-2 local runner.

The implementation lives in ``test2_local_hardened``. Keeping this module as a
thin re-export preserves the public/import contract used by existing tests and
callers while making the scientific hardening changes independently auditable.
"""

from .test2_local_hardened import *  # noqa: F401,F403
