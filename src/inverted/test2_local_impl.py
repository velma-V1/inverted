"""Compatibility surface for the contamination-hardened Test-2 local runner.

The implementation lives in ``test2_local_hardened``. Keeping this module as a
thin re-export preserves the public/import contract used by existing tests and
callers while making the scientific hardening changes independently auditable.
"""

from . import test2_local_hardened as _hardened
from .test2_local_hardened import *  # noqa: F401,F403
from .test2_local_hardened import LOCAL_PHASE_LIMITS, LocalTest2Plan
from .test2_provenance import collect_ollama_provenance


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


def _ollama_context(models) -> tuple[str, tuple[str, ...]] | None:
    model_list = list(models)
    if not model_list or any(str(getattr(model, "provider", "")) != "ollama" for model in model_list):
        return None
    base_urls = {str(getattr(model, "base_url", "")).rstrip("/") for model in model_list}
    if len(base_urls) != 1 or not next(iter(base_urls)):
        raise AssertionError("all Test-2 Ollama adapters must use one explicit base_url")
    return next(iter(base_urls)), tuple(str(getattr(model, "model", "")) for model in model_list)


def _identity_projection(snapshot: dict, model_names: tuple[str, ...]) -> dict:
    rows = snapshot.get("models") or {}
    return {
        "server_version": snapshot.get("server_version"),
        "models": {
            model: {
                "requested_name": (rows.get(model) or {}).get("requested_name"),
                "tag_name": (rows.get(model) or {}).get("tag_name"),
                "tag_digest": (rows.get(model) or {}).get("tag_digest"),
                "tag_size": (rows.get(model) or {}).get("tag_size"),
                "tag_details": (rows.get(model) or {}).get("tag_details"),
                "show_details": (rows.get(model) or {}).get("show_details"),
                "template_sha256": (rows.get(model) or {}).get("template_sha256"),
                "system_sha256": (rows.get(model) or {}).get("system_sha256"),
                "show_payload_sha256": (rows.get(model) or {}).get("show_payload_sha256"),
            }
            for model in model_names
        },
    }


def run_local_campaign(models, run_id: str = "test2-local", hard_limit: int = 480):
    """Run the hardened campaign and close final evidence-lineage gaps."""
    model_list = list(models)
    ollama = _ollama_context(model_list)
    before = None
    if ollama is not None:
        base_url, model_names = ollama
        before = collect_ollama_provenance(base_url, model_names)

    result = _hardened.run_local_campaign(model_list, run_id=run_id, hard_limit=hard_limit)

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

    if ollama is not None:
        base_url, model_names = ollama
        after = collect_ollama_provenance(base_url, model_names)
        result["ollama_provenance"] = {
            "before": before,
            "after": after,
            "identity_match": _identity_projection(before or {}, model_names) == _identity_projection(after, model_names),
        }
    else:
        result["ollama_provenance"] = {"capture_skipped": True, "reason": "non-Ollama test adapter"}
    return result
