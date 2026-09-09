"""Leakage-safe deterministic dataset packaging for V3 Stage 9."""

from __future__ import annotations

from .fine_tuning_core import FineTuningCandidate, FineTuningDataset, FineTuningExample


class FineTuningDatasetCompiler:
    """Package registered Stage-9 examples without generating or copying model content."""

    def compile(
        self,
        *,
        candidate: FineTuningCandidate,
        examples: tuple[FineTuningExample, ...],
        regression_evidence_refs: tuple[str, ...],
        negative_transfer_refs: tuple[str, ...],
    ) -> FineTuningDataset:
        if not isinstance(candidate, FineTuningCandidate):
            raise TypeError("candidate must be FineTuningCandidate")
        if isinstance(examples, (str, bytes, bytearray)) or not isinstance(examples, (list, tuple)):
            raise TypeError("examples must be a sequence")
        rows = tuple(examples)
        if any(not isinstance(item, FineTuningExample) for item in rows):
            raise TypeError("examples must contain FineTuningExample values")
        if not regression_evidence_refs:
            raise ValueError("regression evidence is required for Stage-9 dataset packaging")
        if not negative_transfer_refs:
            raise ValueError("negative-transfer evidence is required for Stage-9 dataset packaging")
        candidate_failures = set(candidate.failure_snapshot_ids)
        row_failures = {item.failure_snapshot_id for item in rows}
        if not row_failures.issubset(candidate_failures):
            raise ValueError("dataset row failure lineage is outside the Stage-9 candidate")
        profiles = {item.base_model_profile_id for item in rows}
        if profiles != {candidate.base_model_profile_id}:
            raise ValueError("dataset rows must preserve the candidate base model profile")
        return FineTuningDataset.create(
            candidate_id=candidate.candidate_id,
            examples=rows,
            regression_evidence_refs=tuple(regression_evidence_refs),
            negative_transfer_refs=tuple(negative_transfer_refs),
        )
