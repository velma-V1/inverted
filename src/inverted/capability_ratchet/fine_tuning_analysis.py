"""Stage-9 D11 qualification analysis; no training or live inference."""

from __future__ import annotations

from .fine_tuning_core import (
    FineTuningCandidate,
    FineTuningDataset,
    FineTuningDisposition,
    FineTuningQualification,
)


class FineTuningAnalyzer:
    def analyze(self, *, candidate: FineTuningCandidate, dataset: FineTuningDataset) -> FineTuningQualification:
        if not isinstance(candidate, FineTuningCandidate):
            raise TypeError("candidate must be FineTuningCandidate")
        if not isinstance(dataset, FineTuningDataset):
            raise TypeError("dataset must be FineTuningDataset")
        if dataset.candidate_id != candidate.candidate_id:
            raise ValueError("dataset candidate lineage mismatch")
        if not candidate.model_internal_residual:
            disposition = FineTuningDisposition.NOT_JUSTIFIED
            risks = ("model-internal ownership is not established",)
            route = "EARLIER_OWNER"
            dataset_id = None
        elif not candidate.cheaper_owners_resolved or not candidate.generalization_complete:
            disposition = FineTuningDisposition.REQUIRES_MORE_EVIDENCE
            risks = ("cheaper-owner or generalization evidence is incomplete",)
            route = "EARLIER_STAGE"
            dataset_id = None
        elif not dataset.train_example_ids or not dataset.eval_example_ids:
            disposition = FineTuningDisposition.REQUIRES_MORE_EVIDENCE
            risks = ("disjoint train/eval evidence is incomplete",)
            route = "STAGE9"
            dataset_id = None
        else:
            disposition = FineTuningDisposition.QUALIFY_CONTROLLED_LANE
            risks = ()
            route = "CONTROLLED_LANE"
            dataset_id = dataset.dataset_id
        evidence = tuple(sorted(set(candidate.generalization_evidence_refs + candidate.tomography_assessment_refs + dataset.regression_evidence_refs + dataset.negative_transfer_refs)))
        return FineTuningQualification.create(
            candidate_id=candidate.candidate_id,
            disposition=disposition,
            evidence_refs=evidence,
            dataset_id=dataset_id,
            unresolved_risks=risks,
            route=route,
        )
