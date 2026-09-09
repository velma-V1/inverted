from __future__ import annotations

import runpy
from pathlib import Path

import inverted.capability_ratchet as cr
from inverted.capability_ratchet.core import PromotionState
from inverted.capability_ratchet.fine_tuning_core import (
    FineTuningDisposition,
    FineTuningPolicy,
)


REQUIRED_PUBLIC = {
    "ControlledTuningPlan",
    "DatasetRole",
    "FineTuningAnalyzer",
    "FineTuningCandidate",
    "FineTuningDataset",
    "FineTuningDatasetCompiler",
    "FineTuningDisposition",
    "FineTuningEligibilityResult",
    "FineTuningEligibilityScanner",
    "FineTuningEligibilityStatus",
    "FineTuningEvidenceStore",
    "FineTuningExample",
    "FineTuningLab",
    "FineTuningLabStatus",
    "FineTuningPlanStatus",
    "FineTuningPlanner",
    "FineTuningPolicy",
    "FineTuningQualification",
    "FineTuningStoreValidation",
    "plan_eligible_fine_tuning",
}


def test_stage9_public_contract_cannot_silently_change() -> None:
    assert REQUIRED_PUBLIC.issubset(set(cr.__all__))
    for name in REQUIRED_PUBLIC:
        assert hasattr(cr, name)
    assert FineTuningPolicy().decision_id == "D11"
    assert FineTuningPolicy().minimum_independent_failures >= 2
    assert FineTuningPolicy().development_model_call_budget == 0
    assert FineTuningPolicy().certification_allowed is False
    assert FineTuningPolicy().deployment_allowed is False
    assert FineTuningPolicy().training_authorized_by_default is False
    assert {item.value for item in FineTuningDisposition}.isdisjoint(
        {item.value for item in PromotionState}
    )
    assert not hasattr(cr, "FineTuningExecutor")
    assert not hasattr(cr, "FineTuningTrainer")


def test_permanent_audit_covers_stage9_fine_tuning_boundaries() -> None:
    text = Path("scripts/audit-v3-replay-foundation.py").read_text(encoding="utf-8")
    required_tokens = (
        "fine_tuning_core.py",
        "fine_tuning_store.py",
        "fine_tuning_eligibility.py",
        "fine_tuning_dataset.py",
        "fine_tuning_planner.py",
        "fine_tuning_analysis.py",
        "fine_tuning_lab.py",
        "fine_tuning_cli.py",
        "test_capability_ratchet_fine_tuning_cli.py",
        "stage9_cli_surface_contract",
        "stage9_zero_call_contract",
        "stage9_no_independent_trainer_contract",
        "stage9_model_internal_owner_contract",
        "stage9_cheaper_owner_veto_contract",
        "stage9_recurrence_contract",
        "stage9_stage8_generalization_gate",
        "stage9_protected_partition_veto_contract",
        "stage9_train_eval_disjoint_contract",
        "stage9_leakage_veto_contract",
        "stage9_observable_target_contract",
        "stage9_regression_negative_transfer_contract",
        "stage9_qualification_not_training_contract",
        "stage9_not_authorized_contract",
        "stage9_stage11_confirmation_contract",
        "stage9_certified_event_count",
    )
    missing = [token for token in required_tokens if token not in text]
    assert not missing, missing


def test_stage9_semantic_audit_is_clean_on_repository_source(tmp_path: Path) -> None:
    audit = runpy.run_path(str(Path("scripts/audit-v3-replay-foundation.py")))
    findings, payload = audit["_stage9_semantic_checks"](Path.cwd(), tmp_path / "replay")
    assert findings == []
    boolean_contracts = {
        key: value
        for key, value in payload.items()
        if key.startswith("stage9_") and key != "stage9_certified_event_count"
    }
    assert boolean_contracts
    assert all(boolean_contracts.values()), boolean_contracts
    assert payload["stage9_certified_event_count"] == 0


def test_stage9_cli_and_sources_have_no_training_execution_surface() -> None:
    sources = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "src/inverted/capability_ratchet/fine_tuning_core.py",
            "src/inverted/capability_ratchet/fine_tuning_store.py",
            "src/inverted/capability_ratchet/fine_tuning_eligibility.py",
            "src/inverted/capability_ratchet/fine_tuning_dataset.py",
            "src/inverted/capability_ratchet/fine_tuning_planner.py",
            "src/inverted/capability_ratchet/fine_tuning_analysis.py",
            "src/inverted/capability_ratchet/fine_tuning_lab.py",
            "src/inverted/capability_ratchet/fine_tuning_cli.py",
        )
    )
    for forbidden in (
        "execute-fine-tuning",
        "train-fine-tuning",
        "--allow-model-calls",
        "FineTuningExecutor",
        "FineTuningTrainer",
        "QwenReplayAdapter",
        "QwenOllamaAdapter",
    ):
        assert forbidden not in sources
