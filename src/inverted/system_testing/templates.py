from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import (
    Disposition,
    InteractionProbe,
    MechanismSpec,
    ResponsibilityOwner,
    SystemTestTemplate,
    TemplateValidationError,
)


SCHEMA_VERSION = 1
PROTECTED_RESPONSIBILITIES = frozenset({
    "CANONICAL_STATE",
    "AUTHORITY",
    "INVARIANTS",
    "IRREVERSIBLE_COMMIT",
    "TRANSACTION_TRUTH",
    "DUPLICATE_EFFECT_PREVENTION",
    "PROVENANCE",
    "FINAL_DETERMINISTIC_VERIFICATION",
})
MODEL_FORBIDDEN_OWNERS = frozenset({
    ResponsibilityOwner.MODEL,
    ResponsibilityOwner.HYBRID,
})

def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemplateValidationError(f"{field} must be an object")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TemplateValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise TemplateValidationError(f"{field} must be a boolean")
    return value


def _require_string_list(value: Any, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TemplateValidationError(f"{field} must be a list")
    if not allow_empty and not value:
        raise TemplateValidationError(f"{field} must not be empty")
    parsed = tuple(_require_string(item, f"{field}[]") for item in value)
    if len(set(parsed)) != len(parsed):
        raise TemplateValidationError(f"{field} contains duplicates")
    return parsed


def _parse_owner(value: Any, field: str) -> ResponsibilityOwner:
    try:
        return ResponsibilityOwner(_require_string(value, field))
    except ValueError as exc:
        raise TemplateValidationError(f"{field} has unknown owner {value!r}") from exc

def _parse_mechanism(raw: Any, index: int) -> MechanismSpec:
    item = _require_mapping(raw, f"mechanisms[{index}]")
    prefix = f"mechanisms[{index}]"
    owner = _parse_owner(item.get("owner"), f"{prefix}.owner")
    responsibilities = _require_string_list(
        item.get("responsibilities"), f"{prefix}.responsibilities"
    )
    for responsibility in responsibilities:
        if responsibility in PROTECTED_RESPONSIBILITIES and owner in MODEL_FORBIDDEN_OWNERS:
            raise TemplateValidationError(
                f"protected responsibility {responsibility} cannot be owned by {owner.value}"
            )
    return MechanismSpec(
        mechanism_id=_require_string(item.get("mechanism_id"), f"{prefix}.mechanism_id"),
        decision_id=_require_string(item.get("decision_id"), f"{prefix}.decision_id"),
        description=_require_string(item.get("description"), f"{prefix}.description"),
        owner=owner,
        responsibilities=responsibilities,
        expected_role=_require_string(item.get("expected_role"), f"{prefix}.expected_role"),
        isolation_required=_require_bool(
            item.get("isolation_required"), f"{prefix}.isolation_required"
        ),
        ablation_required=_require_bool(
            item.get("ablation_required"), f"{prefix}.ablation_required"
        ),
    )

def _parse_interaction(raw: Any, index: int, known: set[str]) -> InteractionProbe:
    item = _require_mapping(raw, f"interactions[{index}]")
    prefix = f"interactions[{index}]"
    members = _require_string_list(item.get("members"), f"{prefix}.members")
    if len(members) < 2:
        raise TemplateValidationError(f"{prefix}.members requires at least two mechanisms")
    unknown = sorted(set(members) - known)
    if unknown:
        raise TemplateValidationError(
            f"{prefix} references unknown mechanism(s): {', '.join(unknown)}"
        )
    return InteractionProbe(
        probe_id=_require_string(item.get("probe_id"), f"{prefix}.probe_id"),
        members=members,
        decision_id=_require_string(item.get("decision_id"), f"{prefix}.decision_id"),
        reason=_require_string(item.get("reason"), f"{prefix}.reason"),
    )


def _parse_dispositions(value: Any) -> tuple[Disposition, ...]:
    raw = _require_string_list(value, "allowed_dispositions")
    try:
        parsed = tuple(Disposition(item) for item in raw)
    except ValueError as exc:
        raise TemplateValidationError("allowed_dispositions contains an unknown value") from exc
    if set(parsed) != set(Disposition):
        raise TemplateValidationError(
            "allowed_dispositions must contain exactly REQUIRED, CONDITIONAL, REDUNDANT, HARMFUL, UNRESOLVED"
        )
    return parsed

def load_system_template(path: str | Path) -> SystemTestTemplate:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateValidationError(f"cannot load system template {source}: {exc}") from exc
    data = _require_mapping(raw, "template")

    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        raise TemplateValidationError(f"schema_version must equal {SCHEMA_VERSION}")

    system_id = _require_string(data.get("system_id"), "system_id")
    factors = _require_string_list(data.get("factors"), "factors", allow_empty=True)
    raw_mechanisms = data.get("mechanisms")
    if not isinstance(raw_mechanisms, list):
        raise TemplateValidationError("mechanisms must be a list")
    mechanisms = tuple(_parse_mechanism(item, i) for i, item in enumerate(raw_mechanisms))
    mechanism_ids = tuple(item.mechanism_id for item in mechanisms)
    if len(set(mechanism_ids)) != len(mechanism_ids):
        raise TemplateValidationError("duplicate mechanism id in template")

    raw_interactions = data.get("interactions")
    if not isinstance(raw_interactions, list):
        raise TemplateValidationError("interactions must be a list")
    interactions = tuple(
        _parse_interaction(item, i, set(mechanism_ids))
        for i, item in enumerate(raw_interactions)
    )
    probe_ids = tuple(probe.probe_id for probe in interactions)
    if len(set(probe_ids)) != len(probe_ids):
        raise TemplateValidationError("duplicate interaction probe id in template")

    if system_id == "RAW":
        if mechanisms:
            raise TemplateValidationError("RAW template cannot contain mechanisms")
        if factors:
            raise TemplateValidationError("RAW template cannot contain factors")
        if interactions:
            raise TemplateValidationError("RAW template cannot contain interactions")
    elif not mechanisms:
        raise TemplateValidationError("non-RAW template requires at least one mechanism")

    return SystemTestTemplate(
        schema_version=version,
        template_id=_require_string(data.get("template_id"), "template_id"),
        system_id=system_id,
        decision_id=_require_string(data.get("decision_id"), "decision_id"),
        description=_require_string(data.get("description"), "description"),
        factors=factors,
        mechanisms=mechanisms,
        interactions=interactions,
        task_families=_require_string_list(data.get("task_families"), "task_families"),
        operating_regions=_require_string_list(data.get("operating_regions"), "operating_regions"),
        primary_metrics=_require_string_list(data.get("primary_metrics"), "primary_metrics"),
        hard_gates=_require_string_list(data.get("hard_gates"), "hard_gates"),
        evidence_fields=_require_string_list(data.get("evidence_fields"), "evidence_fields"),
        allowed_dispositions=_parse_dispositions(data.get("allowed_dispositions")),
    )