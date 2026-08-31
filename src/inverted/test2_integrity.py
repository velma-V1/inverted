from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


_SCREEN_CONDITIONS = {
    ("raw", "regenerate"),
    ("raw", "targeted"),
    ("structured", "regenerate"),
    ("structured", "targeted"),
}


def _trial_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("model") or ""),
        str(row.get("task_id") or ""),
        f"repair_{row.get('feedback_style')}_{row.get('strategy')}",
    )


def _validator_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("model") or ""), str(row.get("task_id") or ""), str(row.get("stage") or ""))


def attach_repair_validator_outcomes(result: dict[str, Any]) -> dict[str, Any]:
    """Attach catastrophic/final-candidate outcomes by causal lineage key.

    The join is intentionally order-independent. Any missing, duplicated, or
    extra model×task×condition validator row fails closed instead of silently
    shifting outcomes between models.
    """
    repair_rows = [row for row in result.get("records", []) if row.get("phase") == "repair_factorial"]
    repair_validators = [
        row for row in result.get("validator_results", [])
        if row.get("phase") == "repair_factorial" and str(row.get("stage", "")).startswith("repair_")
    ]
    validator_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for validator in repair_validators:
        key = _validator_key(validator)
        if not all(key):
            raise AssertionError(f"repair-factorial validator missing model/task/stage lineage: {validator!r}")
        if key in validator_by_key:
            raise AssertionError(f"duplicate repair-factorial validator lineage {key!r}")
        validator_by_key[key] = validator

    trial_keys = [_trial_key(row) for row in repair_rows]
    if any(not key[0] or not key[1] for key in trial_keys):
        raise AssertionError("repair-factorial trial missing model/task lineage")
    if len(set(trial_keys)) != len(trial_keys) or set(trial_keys) != set(validator_by_key):
        raise AssertionError(
            "repair-factorial trial/validator key mismatch: "
            f"trials_only={sorted(set(trial_keys) - set(validator_by_key))!r} "
            f"validators_only={sorted(set(validator_by_key) - set(trial_keys))!r}"
        )
    for trial in repair_rows:
        validator = validator_by_key[_trial_key(trial)]
        trial["candidate_id"] = validator.get("candidate_id")
        trial["catastrophic"] = bool(validator.get("catastrophic"))
    return result


def harden_evidence_integrity(evidence: dict[str, Any]) -> dict[str, Any]:
    """Recompute decisive integrity invariants from the finished evidence packet.

    This deliberately does not trust earlier derived flags. It performs no
    inference/network work and is safe to run immediately before verdicting.
    """
    raw = evidence.get("raw") or {}
    calls = list(raw.get("model_calls") or [])
    trials = list(raw.get("trials") or [])
    audit = evidence.setdefault("diagnostics", {}).setdefault("contamination_audit", {})

    physical = [row for row in calls if not row.get("cache_hit")]
    cached = [row for row in calls if row.get("cache_hit")]
    physical_ids = [str(row.get("call_identity") or "") for row in physical]
    cache_ids = [str(row.get("call_identity") or "") for row in cached]
    physical_counts = Counter(physical_ids)

    duplicate_physical = sorted(identity for identity, count in physical_counts.items() if identity and count > 1)
    missing_physical_identity = sum(1 for identity in physical_ids if not identity)
    unresolved_cache_ids = sorted({identity for identity in cache_ids if identity and identity not in physical_counts})
    missing_cache_identity = sum(1 for identity in cache_ids if not identity)

    audit["duplicate_physical_model_call_ids"] = duplicate_physical
    audit["missing_physical_call_identity_rows"] = missing_physical_identity
    audit["unique_model_call_identity"] = not duplicate_physical and missing_physical_identity == 0
    audit["unresolved_cache_call_ids"] = unresolved_cache_ids
    audit["missing_cache_call_identity_rows"] = missing_cache_identity
    audit["cache_identity_reference_integrity"] = not unresolved_cache_ids and missing_cache_identity == 0
    audit["physical_call_rows"] = len(physical)
    audit["cache_hit_rows"] = len(cached)

    physical_numbers = [row.get("physical_call_number") for row in physical]
    number_integrity = (
        len(physical_numbers) == len(physical)
        and all(type(number) is int and number > 0 for number in physical_numbers)
        and set(physical_numbers) == set(range(1, len(physical) + 1))
    )
    audit["physical_call_number_integrity"] = number_integrity

    master_calls = (evidence.get("master_index") or {}).get("physical_model_calls")
    audit["physical_call_count_matches_master"] = (
        master_calls is not None and int(master_calls) == len(physical)
    )

    screen = [row for row in trials if row.get("phase") == "repair_screen"]
    primary = [row for row in trials if row.get("phase") == "repair_factorial"]
    screen_tasks = {str(row.get("task_id")) for row in screen}
    primary_tasks = {str(row.get("task_id")) for row in primary}
    overlap = sorted(screen_tasks & primary_tasks)
    audit["repair_screen_primary_overlap"] = overlap

    if screen:
        by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in screen:
            by_model[str(row.get("model"))].append(row)
        configured = list(
            (((evidence.get("provenance") or {}).get("config") or {}).get("local") or {}).get("models") or []
        )
        expected_models = set(map(str, configured)) if configured else set(by_model)
        balanced = set(by_model) == expected_models
        for model in expected_models:
            rows = by_model.get(model, [])
            conditions = {(str(row.get("feedback_style")), str(row.get("strategy"))) for row in rows}
            balanced = balanced and len(rows) == 4 and conditions == _SCREEN_CONDITIONS
        audit["repair_screen_condition_balance_ok"] = bool(balanced)
        audit["repair_screen_models"] = sorted(by_model)
        audit["repair_screen_tasks"] = sorted(screen_tasks)
    elif primary:
        audit["repair_screen_condition_balance_ok"] = False
        audit["repair_screen_models"] = []
        audit["repair_screen_tasks"] = []
    else:
        audit["repair_screen_condition_balance_ok"] = None
        audit["repair_screen_models"] = []
        audit["repair_screen_tasks"] = []

    audit["primary_repair_tasks"] = sorted(primary_tasks)
    audit["failed_physical_call_rows"] = sum(
        1 for row in physical if row.get("error_class") or row.get("error_message")
    )
    return evidence
