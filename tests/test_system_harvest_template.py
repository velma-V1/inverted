import json
from pathlib import Path

import pytest

from inverted.system_harvest import TemplateValidationError, load_harvest_template


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "system-harvest-11" / "campaign.json"
EXPECTED = (
    "Codex", "Claude Code / Agent SDK", "Prime Agent", "Pi", "oh-my-cli",
    "SWE-agent", "mini-SWE-agent", "Aider", "AegisEvo", "OpenHands", "Kimi CLI",
)


def test_frozen_manifest_uses_one_pass_evidence_standard_and_escalation():
    template = load_harvest_template(MANIFEST)
    assert template.systems == EXPECTED
    assert len(template.coverage_domains) == 18
    assert template.evidence_layers == ("01_RAW", "02_NORMALIZED", "03_RELATIONSHIPS", "04_DERIVED")
    assert template.one_pass_evidence_standard is True
    assert template.escalation_policy.trigger_on == ("INCORRECT", "STALL")
    assert template.escalation_policy.resume_mode == "CONTINUE_FROM_FAILURE_BOUNDARY"
    assert template.escalation_policy.recursive is True
    assert template.escalation_policy.snapshot_before_recovery_mutation is True
    assert template.require_future_query_probe is True
    assert template.forbid_partial_completion is True


def test_validator_rejects_non_escalating_failure_policy(tmp_path):
    raw = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    raw["escalation_policy"]["resume_mode"] = "RESTART_TASK"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(TemplateValidationError, match="resume_mode"):
        load_harvest_template(bad)


def test_template_freezes_common_behavioral_and_perturbation_batteries():
    template = load_harvest_template(MANIFEST)
    assert len(template.behavioral_battery) >= 30
    assert {
        "AMBIGUOUS_REQUIREMENT", "FLAKY_TESTS", "INTERRUPTED_EXECUTION",
        "PARTIAL_MUTATION", "CONTEXT_PRESSURE", "IRREVERSIBLE_ACTION_BOUNDARY",
        "REPEATED_FAILURE_TRAP", "RESUME_AFTER_INTERRUPTION",
    }.issubset(template.behavioral_battery)
    assert {
        "CONTEXT_AMOUNT", "CONTEXT_ORDER", "STALE_CONTEXT", "DISABLE_MEMORY",
        "DISABLE_PLANNING", "DISABLE_VERIFIER", "BREAK_TOOL", "REMOVE_NETWORK",
        "CHANGE_MODEL", "TOKEN_CALL_PRESSURE", "CONFLICTING_STATE", "INTERRUPTION_TIMING",
    }.issubset(template.perturbation_battery)


def test_escalation_capsules_are_a_mandatory_evidence_channel():
    template = load_harvest_template(MANIFEST)
    assert "ESCALATION_CAPSULES" in template.required_evidence_channels


def test_validator_rejects_missing_escalation_capsule_channel(tmp_path):
    raw = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    raw["required_evidence_channels"] = [
        item for item in raw["required_evidence_channels"] if item != "ESCALATION_CAPSULES"
    ]
    bad = tmp_path / "bad-missing-escalation-channel.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(TemplateValidationError, match="ESCALATION_CAPSULES"):
        load_harvest_template(bad)
