"""Adaptive Stage-5 surface orchestration over the canonical replay kernel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .causal_store import CausalEvidenceStore
from .core import ReplayResult
from .replay import ReplayAdapter, ReplayExecutor
from .replay_store import ReplayStore
from .surface_analysis import SurfaceAnalyzer
from .surface_core import OperatingSurfaceProfile, SurfaceObservation, SurfaceStudy
from .surface_evidence import SurfaceEvidenceCompiler
from .surface_interventions import SurfaceInterventionCompiler
from .surface_planner import SurfacePlan, SurfacePlanner
from .surface_store import SurfaceEvidenceStore


@dataclass(frozen=True)
class SurfaceStepResult:
    plan: SurfacePlan
    replay_results: tuple[ReplayResult, ...]
    observations: tuple[SurfaceObservation, ...]
    profile: OperatingSurfaceProfile
    next_plan: SurfacePlan
    child_failure_snapshot_ids: tuple[str, ...]
    model_calls_are_fake_only: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_results", tuple(self.replay_results))
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(
            self, "child_failure_snapshot_ids", tuple(self.child_failure_snapshot_ids)
        )
        if type(self.model_calls_are_fake_only) is not bool:
            raise TypeError("model_calls_are_fake_only must be boolean")


class OperatingSurfaceLab:
    """Prepare and execute one adaptive operating-surface step.

    Planning is zero-call and may only materialize reusable scientific metadata.
    Execution accepts injected replay adapters and delegates every model call to
    the canonical :class:`ReplayExecutor`; this module never constructs a live
    model adapter or performs an automatic retry.
    """

    def __init__(
        self,
        replay_store: ReplayStore,
        causal_store: CausalEvidenceStore,
        surface_store: SurfaceEvidenceStore,
        evidence_compiler: SurfaceEvidenceCompiler,
        planner: SurfacePlanner,
        intervention_compiler: SurfaceInterventionCompiler,
        analyzer: SurfaceAnalyzer,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        if not isinstance(surface_store, SurfaceEvidenceStore):
            raise TypeError("surface_store must be SurfaceEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store
        self.surface_store = surface_store
        self.evidence_compiler = evidence_compiler
        self.planner = planner
        self.intervention_compiler = intervention_compiler
        self.analyzer = analyzer

    def _study(self, study_id: str) -> SurfaceStudy:
        if not isinstance(study_id, str) or not study_id.strip():
            raise ValueError("study_id is required")
        matches = [item for item in self.surface_store.studies() if item.study_id == study_id]
        if len(matches) != 1:
            raise ValueError("surface study must resolve to exactly one stored study")
        return matches[0]

    def _validate_stores(self) -> None:
        if not self.replay_store.validate().ok:
            raise ValueError("replay store integrity validation failed")
        if not self.causal_store.validate().ok:
            raise ValueError("causal evidence store integrity validation failed")
        if not self.surface_store.validate().ok:
            raise ValueError("surface evidence store integrity validation failed")

    def prepare(self, study_id: str, *, max_new_points: int = 2) -> SurfacePlan:
        self._validate_stores()
        study = self._study(study_id)
        return self.planner.plan_next(study, max_new_points=max_new_points)

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

    @staticmethod
    def _request_id(point) -> str:
        return f"surface-replay-{point.surface_point_id}"

    def execute(
        self,
        plan: SurfacePlan,
        adapters: Mapping[str, ReplayAdapter],
    ) -> SurfaceStepResult:
        if not isinstance(plan, SurfacePlan):
            raise TypeError("plan must be SurfacePlan")
        if plan.stop_reason is not None or not plan.points:
            raise ValueError("stopped surface plan has no executable points")
        if not isinstance(adapters, Mapping) or not adapters:
            raise ValueError("execute requires injected replay adapters")
        self._validate_stores()

        study_ids = {point.study_id for point in plan.points}
        if len(study_ids) != 1:
            raise ValueError("surface plan points must belong to one study")
        study = self._study(next(iter(study_ids)))
        for point in plan.points:
            if point.study_id != study.study_id:
                raise ValueError("surface plan point study lineage drifted")

        requests = tuple(
            self.intervention_compiler.compile_point(
                study,
                point,
                request_id=self._request_id(point),
                decision_id=study.decision_id,
            )[1]
            for point in plan.points
        )
        executor = ReplayExecutor(self.replay_store, adapters)
        results = tuple(executor.execute(request) for request in requests)

        all_observations = self.evidence_compiler.same_state_observations(study)
        result_ids = {result.replay_result_id for result in results}
        observations = tuple(
            row for row in all_observations
            if result_ids.intersection(row.replay_result_ids)
        )
        if not observations:
            raise ValueError("surface execution produced no same-state surface observations")

        profile = self.analyzer.analyze(study.study_id)
        next_plan = self.planner.plan_next(study)
        child_ids = tuple(
            result.child_failure_snapshot_id
            for result in results
            if result.child_failure_snapshot_id is not None
        )
        return SurfaceStepResult(
            plan=plan,
            replay_results=results,
            observations=observations,
            profile=profile,
            next_plan=next_plan,
            child_failure_snapshot_ids=child_ids,
            model_calls_are_fake_only=self._all_fake(adapters),
        )
