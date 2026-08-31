"""Compatibility surface for the contamination-hardened Test-2 local runner.

The implementation lives in ``test2_local_hardened``. Keeping this module as a
thin re-export preserves the public/import contract used by existing tests and
callers while making the scientific hardening changes independently auditable.
"""

from . import test2_local_hardened as _hardened
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


def run_local_campaign(models, run_id: str = "test2-local", hard_limit: int = 480):
    """Run the hardened campaign and close the repair catastrophic-telemetry gap.

    ``test2_local_hardened`` already records a validator result immediately
    after every repair-factorial trial. The repair trial and validator ledgers
    are deliberately order-preserving, so enrich each repair trial from its
    matched validator row and fail closed if that lineage is ever broken.
    """
    result = _hardened.run_local_campaign(models, run_id=run_id, hard_limit=hard_limit)
    repair_rows = [row for row in result.get("records", []) if row.get("phase") == "repair_factorial"]
    repair_validators = [
        row for row in result.get("validator_results", [])
        if row.get("phase") == "repair_factorial" and str(row.get("stage", "")).startswith("repair_")
    ]
    if len(repair_rows) != len(repair_validators):
        raise AssertionError(
            f"repair-factorial trial/validator lineage mismatch: {len(repair_rows)} trials vs {len(repair_validators)} validators"
        )
    for trial, validator in zip(repair_rows, repair_validators):
        expected_stage = f"repair_{trial.get('feedback_style')}_{trial.get('strategy')}"
        if str(validator.get("task_id")) != str(trial.get("task_id")) or str(validator.get("stage")) != expected_stage:
            raise AssertionError(
                "repair-factorial trial/validator ordering mismatch: "
                f"trial={trial.get('task_id')} {expected_stage} validator={validator.get('task_id')} {validator.get('stage')}"
            )
        trial["catastrophic"] = bool(validator.get("catastrophic"))
    return result
