"""Thin Stage-9 orchestration over deterministic evidence components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fine_tuning_analysis import FineTuningAnalyzer
from .fine_tuning_dataset import FineTuningDatasetCompiler
from .fine_tuning_eligibility import FineTuningEligibilityScanner, plan_eligible_fine_tuning
from .fine_tuning_planner import FineTuningPlanner
from .fine_tuning_store import FineTuningEvidenceStore


@dataclass(frozen=True)
class FineTuningLabStatus:
    model_calls: int
    historical_status: str
    eligible_candidate_ids: tuple[str, ...]


class FineTuningLab:
    """Stage-9 coordinator. It intentionally exposes no training execution method."""

    def __init__(
        self,
        *,
        scanner: FineTuningEligibilityScanner,
        store: FineTuningEvidenceStore,
        dataset_compiler: FineTuningDatasetCompiler | None = None,
        analyzer: FineTuningAnalyzer | None = None,
        planner: FineTuningPlanner | None = None,
    ) -> None:
        if not isinstance(scanner, FineTuningEligibilityScanner):
            raise TypeError("scanner must be FineTuningEligibilityScanner")
        if not isinstance(store, FineTuningEvidenceStore):
            raise TypeError("store must be FineTuningEvidenceStore")
        self.scanner = scanner
        self.store = store
        self.dataset_compiler = dataset_compiler or FineTuningDatasetCompiler()
        self.analyzer = analyzer or FineTuningAnalyzer()
        self.planner = planner or FineTuningPlanner()

    def status(self) -> FineTuningLabStatus:
        boundary = plan_eligible_fine_tuning(self.scanner)
        return FineTuningLabStatus(
            model_calls=0,
            historical_status=str(boundary["status"]),
            eligible_candidate_ids=tuple(boundary["eligible_candidate_ids"]),
        )

    def register_scanned_candidates(self) -> tuple[str, ...]:
        ids = []
        for row in self.scanner.scan():
            if row.candidate is not None:
                ids.append(self.store.append_candidate(row.candidate))
        return tuple(ids)
