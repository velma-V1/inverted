from __future__ import annotations

from pathlib import Path

import inverted.capability_ratchet as cr


def test_stage6_bootstrap_is_stable_public_contract() -> None:
    required = {
        "MutationBootstrapPlan",
        "MutationBootstrapResult",
        "plan_eligible_mutations",
    }
    assert required.issubset(set(cr.__all__))
    for name in required:
        assert hasattr(cr, name)


def test_stage6_completion_workflow_uses_true_mutation_bootstrap() -> None:
    text = Path(".github/workflows/v3-stage6-completion.yml").read_text(encoding="utf-8")
    assert "python -m inverted.capability_ratchet.cli plan-mutations" in text
    assert "--auto-eligible" in text
    assert "historical-stage6-prerequisites.json" in text


def test_permanent_audit_covers_auto_planning_and_protected_veto() -> None:
    text = Path("scripts/audit-v3-replay-foundation.py").read_text(encoding="utf-8")
    for token in (
        "stage6_auto_plan_contract",
        "stage6_protected_failure_veto_contract",
        "MutationBootstrapPlan",
        "MutationBootstrapResult",
        "plan_eligible_mutations",
        "mutation_bootstrap.py",
    ):
        assert token in text
