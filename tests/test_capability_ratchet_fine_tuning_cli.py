from __future__ import annotations

from inverted.capability_ratchet import (
    ControlledTuningPlan,
    FineTuningAnalyzer,
    FineTuningCandidate,
    FineTuningDataset,
    FineTuningDatasetCompiler,
    FineTuningDisposition,
    FineTuningEligibilityScanner,
    FineTuningEvidenceStore,
    FineTuningExample,
    FineTuningPlanner,
    FineTuningPolicy,
    FineTuningQualification,
)
from inverted.capability_ratchet.fine_tuning_cli import FINE_TUNING_COMMANDS


def test_stage9_public_api_exports_scientific_contracts() -> None:
    assert all(value is not None for value in (
        ControlledTuningPlan, FineTuningAnalyzer, FineTuningCandidate, FineTuningDataset,
        FineTuningDatasetCompiler, FineTuningDisposition, FineTuningEligibilityScanner,
        FineTuningEvidenceStore, FineTuningExample, FineTuningPlanner, FineTuningPolicy,
        FineTuningQualification,
    ))


def test_stage9_cli_is_query_plan_only_with_no_train_or_execute_surface() -> None:
    assert FINE_TUNING_COMMANDS == frozenset({
        "scan-fine-tuning-eligibility",
        "plan-fine-tuning",
        "show-fine-tuning-candidate",
        "show-fine-tuning-qualification",
        "export-fine-tuning-dataset",
    })
    lowered = " ".join(FINE_TUNING_COMMANDS).lower()
    assert "train-fine" not in lowered
    assert "execute-fine" not in lowered
