from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .escalation import REQUIRED_ESCALATION_SECTIONS
from .types import EscalationPolicy, HarvestTemplate, TemplateValidationError


EXPECTED_SYSTEMS = (
    "Codex", "Claude Code / Agent SDK", "Prime Agent", "Pi", "oh-my-cli",
    "SWE-agent", "mini-SWE-agent", "Aider", "AegisEvo", "OpenHands", "Kimi CLI",
)
EXPECTED_LAYERS = ("01_RAW", "02_NORMALIZED", "03_RELATIONSHIPS", "04_DERIVED")


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TemplateValidationError(f"{field} must be a non-empty list")
    items = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if len(items) != len(value) or len(set(items)) != len(items):
        raise TemplateValidationError(f"{field} must contain unique non-empty strings")
    return items


def _parse_escalation_policy(data: dict[str, Any]) -> EscalationPolicy:
    if "retry_policy" in data:
        raise TemplateValidationError("retry_policy is deprecated; failures must escalate")
    raw = data.get("escalation_policy")
    if not isinstance(raw, dict):
        raise TemplateValidationError("escalation_policy must be an object")
    trigger_on = _strings(raw.get("trigger_on"), "escalation_policy.trigger_on")
    if trigger_on != ("INCORRECT", "STALL"):
        raise TemplateValidationError("escalation_policy.trigger_on must be exactly INCORRECT, STALL")
    resume_mode = raw.get("resume_mode")
    if resume_mode != "CONTINUE_FROM_FAILURE_BOUNDARY":
        raise TemplateValidationError("escalation_policy.resume_mode must equal CONTINUE_FROM_FAILURE_BOUNDARY")
    if raw.get("recursive") is not True:
        raise TemplateValidationError("escalation_policy.recursive must be true")
    if raw.get("snapshot_before_recovery_mutation") is not True:
        raise TemplateValidationError("escalation_policy.snapshot_before_recovery_mutation must be true")
    sections = _strings(raw.get("required_snapshot_sections"), "escalation_policy.required_snapshot_sections")
    missing = sorted(set(REQUIRED_ESCALATION_SECTIONS) - set(sections))
    if missing:
        raise TemplateValidationError(
            "escalation_policy.required_snapshot_sections missing: " + ", ".join(missing)
        )
    return EscalationPolicy(trigger_on, resume_mode, True, True, sections)


def load_harvest_template(path: str | Path) -> HarvestTemplate:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateValidationError(f"cannot load harvest template: {exc}") from exc
    if data.get("schema_version") != 1:
        raise TemplateValidationError("schema_version must equal 1")
    systems = _strings(data.get("systems"), "systems")
    if systems != EXPECTED_SYSTEMS:
        raise TemplateValidationError("systems must exactly match the frozen eleven-system set")
    layers = _strings(data.get("evidence_layers"), "evidence_layers")
    if layers != EXPECTED_LAYERS:
        raise TemplateValidationError("evidence_layers must preserve all four evidence tiers")
    if data.get("one_pass_evidence_standard") is not True:
        raise TemplateValidationError("one_pass_evidence_standard must be true")
    escalation_policy = _parse_escalation_policy(data)

    completion = data.get("completion_policy")
    if not isinstance(completion, dict):
        raise TemplateValidationError("completion_policy must be an object")
    required_true = (
        "require_all_systems", "require_future_query_probe",
        "require_verified_manifests", "forbid_partial_completion",
    )
    for field in required_true:
        if completion.get(field) is not True:
            raise TemplateValidationError(f"{field} must be true")

    campaign_id = data.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise TemplateValidationError("campaign_id must be non-empty")
    required_channels = _strings(data.get("required_evidence_channels"), "required_evidence_channels")
    if "ESCALATION_CAPSULES" not in required_channels:
        raise TemplateValidationError("required_evidence_channels must include ESCALATION_CAPSULES")
    return HarvestTemplate(
        schema_version=1, campaign_id=campaign_id.strip(), systems=systems,
        evidence_layers=layers,
        coverage_domains=_strings(data.get("coverage_domains"), "coverage_domains"),
        behavioral_battery=_strings(data.get("behavioral_battery"), "behavioral_battery"),
        perturbation_battery=_strings(data.get("perturbation_battery"), "perturbation_battery"),
        required_evidence_channels=required_channels,
        one_pass_evidence_standard=True, escalation_policy=escalation_policy,
        require_all_systems=True, require_future_query_probe=True,
        require_verified_manifests=True, forbid_partial_completion=True,
    )
