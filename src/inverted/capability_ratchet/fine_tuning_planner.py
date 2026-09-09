"""Bounded zero-call controlled-lane planning for V3 Stage 9."""

from __future__ import annotations

from typing import Any, Mapping

from .fine_tuning_core import (
    ControlledTuningPlan,
    FineTuningDataset,
    FineTuningDisposition,
    FineTuningQualification,
)


class FineTuningPlanner:
    def plan(
        self,
        *,
        qualification: FineTuningQualification,
        dataset: FineTuningDataset,
        objective: str,
        hyperparameter_envelope: Mapping[str, Any],
        physical_training_budget_ceiling: int,
        evaluation_refs: tuple[str, ...],
        regression_refs: tuple[str, ...],
        abort_criteria: tuple[str, ...],
        rollback_rule: str,
    ) -> ControlledTuningPlan:
        if not isinstance(qualification, FineTuningQualification):
            raise TypeError("qualification must be FineTuningQualification")
        if qualification.disposition is not FineTuningDisposition.QUALIFY_CONTROLLED_LANE:
            raise ValueError("controlled tuning may only be planned after QUALIFY_CONTROLLED_LANE")
        if not isinstance(dataset, FineTuningDataset):
            raise TypeError("dataset must be FineTuningDataset")
        if qualification.dataset_id != dataset.dataset_id or qualification.candidate_id != dataset.candidate_id:
            raise ValueError("qualification/dataset lineage mismatch")
        profiles = {item.base_model_profile_id for item in dataset.examples}
        if len(profiles) != 1:
            raise ValueError("controlled lane requires one frozen base model profile")
        return ControlledTuningPlan.create(
            qualification_id=qualification.qualification_id,
            dataset_id=dataset.dataset_id,
            base_model_profile_id=next(iter(profiles)),
            objective=objective,
            hyperparameter_envelope=hyperparameter_envelope,
            physical_training_budget_ceiling=physical_training_budget_ceiling,
            evaluation_refs=evaluation_refs,
            regression_refs=regression_refs,
            abort_criteria=abort_criteria,
            rollback_rule=rollback_rule,
        )
