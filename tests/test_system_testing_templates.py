from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.system_testing import (
    Disposition,
    ResponsibilityOwner,
    TemplateValidationError,
    load_system_template,
)


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "template_id": "test-system-v1",
        "system_id": "TEST_SYSTEM",
        "decision_id": "DECIDE-TEST-SYSTEM",
        "description": "A minimal causal system template.",
        "factors": ["TEST_FACTOR"],
        "mechanisms": [            {
                "mechanism_id": "M1",
                "decision_id": "DECIDE-M1",
                "description": "Test mechanism one.",
                "owner": "SYSTEM",
                "responsibilities": ["WORKING_CONTEXT"],
                "expected_role": "candidate support",
                "isolation_required": True,
                "ablation_required": True,
            },
            {
                "mechanism_id": "M2",
                "decision_id": "DECIDE-M2",
                "description": "Test mechanism two.",
                "owner": "VERIFIER",
                "responsibilities": ["SEMANTIC_VERIFICATION"],
                "expected_role": "independent checking",
                "isolation_required": False,
                "ablation_required": True,
            },
        ],
        "interactions": [
            {
                "probe_id": "M1_X_M2",
                "members": ["M1", "M2"],
                "decision_id": "DECIDE-M1-X-M2",
                "reason": "Determine whether the mechanisms compound or overlap.",
            }
        ],        "task_families": ["state", "policy", "reconciliation"],
        "operating_regions": ["GLOBAL_INTERACTION", "EVIDENCE_TRUST"],
        "primary_metrics": ["verified_success", "catastrophic_failure"],
        "hard_gates": ["no_catastrophic_regression"],
        "evidence_fields": ["active_mechanisms", "model_visible_input", "verified_outcome"],
        "allowed_dispositions": [
            "REQUIRED",
            "CONDITIONAL",
            "REDUNDANT",
            "HARMFUL",
            "UNRESOLVED",
        ],
    }


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "template.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_system_template_parses_immutable_contract(tmp_path):
    template = load_system_template(_write(tmp_path, _manifest()))

    assert template.system_id == "TEST_SYSTEM"
    assert template.factors == ("TEST_FACTOR",)
    assert tuple(m.mechanism_id for m in template.mechanisms) == ("M1", "M2")
    assert template.mechanisms[0].owner is ResponsibilityOwner.SYSTEM
    assert set(template.allowed_dispositions) == set(Disposition)
    assert template.interactions[0].members == ("M1", "M2")

def test_raw_template_cannot_contain_support_mechanisms(tmp_path):
    data = _manifest()
    data["system_id"] = "RAW"
    data["factors"] = []

    with pytest.raises(TemplateValidationError, match="RAW.*mechanisms"):
        load_system_template(_write(tmp_path, data))


def test_duplicate_mechanism_ids_fail_preflight(tmp_path):
    data = _manifest()
    data["mechanisms"][1]["mechanism_id"] = "M1"

    with pytest.raises(TemplateValidationError, match="duplicate mechanism"):
        load_system_template(_write(tmp_path, data))


def test_interaction_cannot_reference_unknown_mechanism(tmp_path):
    data = _manifest()
    data["interactions"][0]["members"] = ["M1", "UNKNOWN"]

    with pytest.raises(TemplateValidationError, match="unknown mechanism"):
        load_system_template(_write(tmp_path, data))


def test_unknown_responsibility_owner_fails_preflight(tmp_path):
    data = _manifest()
    data["mechanisms"][0]["owner"] = "MAGIC"

    with pytest.raises(TemplateValidationError, match="owner"):
        load_system_template(_write(tmp_path, data))

def test_model_cannot_own_protected_authority_responsibility(tmp_path):
    data = _manifest()
    data["mechanisms"][0]["owner"] = "MODEL"
    data["mechanisms"][0]["responsibilities"] = ["AUTHORITY"]

    with pytest.raises(TemplateValidationError, match="AUTHORITY.*MODEL"):
        load_system_template(_write(tmp_path, data))


def test_required_flags_must_be_real_booleans(tmp_path):
    data = _manifest()
    data["mechanisms"][0]["ablation_required"] = 1

    with pytest.raises(TemplateValidationError, match="ablation_required"):
        load_system_template(_write(tmp_path, data))


def test_allowed_dispositions_must_preserve_full_project_vocabulary(tmp_path):
    data = _manifest()
    data["allowed_dispositions"].remove("HARMFUL")

    with pytest.raises(TemplateValidationError, match="allowed_dispositions"):
        load_system_template(_write(tmp_path, data))


def test_non_raw_template_requires_at_least_one_mechanism(tmp_path):
    data = _manifest()
    data["mechanisms"] = []
    data["interactions"] = []

    with pytest.raises(TemplateValidationError, match="non-RAW.*mechanism"):
        load_system_template(_write(tmp_path, data))