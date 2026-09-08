"""Stage-7 orchestration over the canonical replay executor."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from .causal_core import InterventionDefinition
from .core import FailureFixture, ReplayResult
from .replay import ReplayAdapter, ReplayExecutor
from .replay_store import ReplayStore
from .tomography_analysis import TomographyAnalyzer
from .tomography_core import TomographyOutcome, TomographyProbe, TomographyProfile, TomographyStudy, stable_id
from .tomography_replay import TomographyReplayCompiler
from .tomography_store import TomographyEvidenceStore


@dataclass(frozen=True)
class TomographyStepResult:
    study: TomographyStudy
    replay_results: tuple[ReplayResult, ...]
    outcomes: tuple[TomographyOutcome, ...]
    profile: TomographyProfile
    child_failure_snapshot_ids: tuple[str, ...]
    model_calls_are_fake_only: bool


class TomographyLab:
    """Execute already-planned probes; never constructs a model/tool transport."""

    def __init__(
        self,
        replay_store: ReplayStore,
        tomography_store: TomographyEvidenceStore,
        *,
        analyzer: TomographyAnalyzer | None = None,
        compiler: TomographyReplayCompiler | None = None,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(tomography_store, TomographyEvidenceStore):
            raise TypeError("tomography_store must be TomographyEvidenceStore")
        self.replay_store = replay_store
        self.tomography_store = tomography_store
        self.analyzer = TomographyAnalyzer() if analyzer is None else analyzer
        self.compiler = TomographyReplayCompiler() if compiler is None else compiler

    def _root_failure_id(self, fixture: FailureFixture) -> str:
        current = fixture
        seen: set[str] = set()
        while current.parent_failure_snapshot_id is not None:
            if current.failure_snapshot_id in seen:
                raise ValueError("failure lineage cycle")
            seen.add(current.failure_snapshot_id)
            current = self.replay_store.get_failure(current.parent_failure_snapshot_id)
        return current.failure_snapshot_id

    @staticmethod
    def _all_fake(adapters: Mapping[str, ReplayAdapter]) -> bool:
        if not adapters:
            return False
        try:
            return all(
                str(adapter.runtime_provenance().get("provider", "")).casefold() == "fake"
                for adapter in adapters.values()
            )
        except Exception:
            return False

    def execute(
        self,
        study: TomographyStudy,
        probes: tuple[TomographyProbe, ...],
        interventions: Mapping[str, InterventionDefinition],
        adapters: Mapping[str, ReplayAdapter],
        *,
        skill_related_success_count: int = 0,
        external_supports_exhausted: bool = False,
    ) -> TomographyStepResult:
        if not isinstance(study, TomographyStudy):
            raise TypeError("study must be TomographyStudy")
        probes = tuple(probes)
        if tuple(item.probe_id for item in probes) != study.probe_ids:
            raise ValueError("executable probes must exactly match study probe_ids")
        if not adapters:
            raise ValueError("execute requires injected replay adapters")
        if not self.replay_store.validate().ok:
            raise ValueError("replay store integrity validation failed")
        fixture = self.replay_store.get_failure(study.failure_snapshot_id)
        if fixture.state_hash != study.parent_state_hash or fixture.partition != study.partition:
            raise ValueError("tomography study differs from canonical parent failure")

        executor = ReplayExecutor(self.replay_store, adapters)
        results: list[ReplayResult] = []
        outcomes: list[TomographyOutcome] = []
        for probe in probes:
            try:
                intervention = interventions[probe.intervention_id]
            except KeyError as exc:
                raise ValueError(f"missing intervention for tomography probe {probe.probe_id}") from exc
            request = self.compiler.compile_request(
                study,
                probe,
                intervention,
                root_failure_snapshot_id=self._root_failure_id(fixture),
                source_model_id=fixture.source_model_id,
                source_model_digest=fixture.source_model_digest,
                request_id=f"tomography-replay-{probe.probe_id}",
            )
            result = executor.execute(request)
            results.append(result)
            raw_score = result.metrics.get("score") if isinstance(result.metrics, Mapping) else None
            score = float(raw_score) if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool) else (1.0 if result.semantic_pass and result.contract_pass else 0.0)
            comparison_refs = tuple(dict.fromkeys(study.baseline_evidence_refs + tuple(
                prior.replay_result_id for prior in results[:-1]
            )))
            first_divergence = result.failure_classes[0] if result.failure_classes else None
            outcome = TomographyOutcome(
                outcome_id=stable_id("tomography-outcome", {
                    "study_id": study.study_id,
                    "probe_id": probe.probe_id,
                    "replay_result_id": result.replay_result_id,
                }),
                study_id=study.study_id,
                probe_id=probe.probe_id,
                replay_result_id=result.replay_result_id,
                semantic_success=result.semantic_pass,
                contract_valid=result.contract_pass,
                score=score,
                first_divergence=first_divergence,
                comparison_refs=comparison_refs,
                protected_regression=bool(probe.protected and not (result.semantic_pass and result.contract_pass)),
                child_failure_snapshot_id=result.child_failure_snapshot_id,
            )
            self.tomography_store.append_outcome(outcome)
            outcomes.append(outcome)

        profile = self.analyzer.analyze(
            study,
            probes,
            tuple(outcomes),
            skill_related_success_count=skill_related_success_count,
            external_supports_exhausted=external_supports_exhausted,
        )
        self.tomography_store.append_profile(profile)
        validation = self.tomography_store.validate()
        if not validation.ok:
            raise ValueError(f"tomography metadata integrity validation failed: {validation}")
        child_ids = tuple(
            item.child_failure_snapshot_id
            for item in results
            if item.child_failure_snapshot_id is not None
        )
        return TomographyStepResult(
            study=study,
            replay_results=tuple(results),
            outcomes=tuple(outcomes),
            profile=profile,
            child_failure_snapshot_ids=child_ids,
            model_calls_are_fake_only=self._all_fake(adapters),
        )
