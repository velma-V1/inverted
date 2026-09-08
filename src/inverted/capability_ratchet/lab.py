"""Reusable zero-call planning and injected-adapter execution for one failure family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .autopsy import AutopsyReport, FailureAutopsy
from .causal_core import InterventionDefinition, InterventionKind
from .causal_store import CausalEvidenceStore
from .core import FailureFixture, ReplayRequest, ReplayResult
from .interventions import InterventionGenerator
from .mechanisms import MechanismAssessment, MechanismLocalizer
from .replay import ReplayAdapter, ReplayExecutor
from .replay_store import ReplayStore
from .tournament import TournamentPlan, TournamentPlanner


@dataclass(frozen=True)
class FailureResearchProgram:
    failure_snapshot_id: str
    root_failure_snapshot_id: str
    fixture: FailureFixture
    autopsy: AutopsyReport
    interventions: tuple[InterventionDefinition, ...]
    tournament: TournamentPlan
    replay_requests: tuple[ReplayRequest, ...]
    projected_physical_calls: int
    model_calls: int = 0

    def __post_init__(self) -> None:
        if not self.failure_snapshot_id:
            raise ValueError("failure_snapshot_id is required")
        if not self.root_failure_snapshot_id:
            raise ValueError("root_failure_snapshot_id is required")
        if self.fixture.failure_snapshot_id != self.failure_snapshot_id:
            raise ValueError("program fixture/failure identity mismatch")
        if self.autopsy.failure_snapshot_id != self.failure_snapshot_id:
            raise ValueError("program autopsy/failure identity mismatch")
        if self.tournament.failure_snapshot_id != self.failure_snapshot_id:
            raise ValueError("program tournament/failure identity mismatch")
        object.__setattr__(self, "interventions", tuple(self.interventions))
        object.__setattr__(self, "replay_requests", tuple(self.replay_requests))
        if (
            not isinstance(self.projected_physical_calls, int)
            or isinstance(self.projected_physical_calls, bool)
            or self.projected_physical_calls < 0
        ):
            raise ValueError("projected_physical_calls must be a non-negative integer")
        if self.model_calls != 0:
            raise ValueError("prepared research programs must record zero model calls")


@dataclass(frozen=True)
class FailureResearchResult:
    program: FailureResearchProgram
    replay_results: tuple[ReplayResult, ...]
    target_results: tuple[ReplayResult, ...]
    sham_results: tuple[ReplayResult, ...]
    assessment: MechanismAssessment
    child_failure_snapshot_ids: tuple[str, ...]
    model_calls_are_fake_only: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_results", tuple(self.replay_results))
        object.__setattr__(self, "target_results", tuple(self.target_results))
        object.__setattr__(self, "sham_results", tuple(self.sham_results))
        object.__setattr__(
            self, "child_failure_snapshot_ids", tuple(self.child_failure_snapshot_ids)
        )
        if type(self.model_calls_are_fake_only) is not bool:
            raise TypeError("model_calls_are_fake_only must be boolean")


class FailureLab:
    """Turn an immutable failure snapshot into a replayable causal research program.

    ``prepare`` is inspection/planning only. ``execute`` accepts already-created
    adapters and delegates every model replay to the canonical ``ReplayExecutor``.
    This class never imports or constructs a live model adapter.
    """

    def __init__(
        self,
        replay_store: ReplayStore,
        causal_store: CausalEvidenceStore,
        autopsy: FailureAutopsy,
        intervention_generator: InterventionGenerator,
        tournament_planner: TournamentPlanner,
        localizer: MechanismLocalizer,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store
        self.autopsy = autopsy
        self.intervention_generator = intervention_generator
        self.tournament_planner = tournament_planner
        self.localizer = localizer

    def _root_failure_id(self, fixture: FailureFixture) -> str:
        current = fixture
        visited: set[str] = set()
        while current.parent_failure_snapshot_id is not None:
            if current.failure_snapshot_id in visited:
                raise ValueError("failure lineage cycle")
            visited.add(current.failure_snapshot_id)
            current = self.replay_store.get_failure(current.parent_failure_snapshot_id)
        return current.failure_snapshot_id

    @staticmethod
    def _request_id(branch_id: str) -> str:
        return f"lab-replay-{branch_id}"

    @staticmethod
    def _decision_id(branch_id: str) -> str:
        return f"lab-decision-{branch_id}"

    def prepare(self, failure_snapshot_id: str) -> FailureResearchProgram:
        if not isinstance(failure_snapshot_id, str) or not failure_snapshot_id.strip():
            raise ValueError("failure_snapshot_id is required")
        replay_validation = self.replay_store.validate()
        if not replay_validation.ok:
            raise ValueError("replay store integrity validation failed")

        fixture = self.replay_store.get_failure(failure_snapshot_id)
        report = self.autopsy.analyze(fixture)

        interventions: list[InterventionDefinition] = []
        seen: set[str] = set()
        for hypothesis in report.hypotheses:
            for target in self.intervention_generator.generate(fixture, hypothesis):
                candidates = (target, self.intervention_generator.make_matched_sham(target))
                for intervention in candidates:
                    if intervention is None or intervention.intervention_id in seen:
                        continue
                    interventions.append(intervention)
                    seen.add(intervention.intervention_id)

        plan = self.tournament_planner.plan(
            fixture,
            report.hypotheses,
            tuple(interventions),
            reproducibility_known=True,
        )
        interventions_by_id = {item.intervention_id: item for item in interventions}
        requests: list[ReplayRequest] = []
        for branch in plan.branches:
            if branch.mode not in {"TARGET", "SHAM"}:
                continue
            if len(branch.intervention_ids) != 1:
                raise ValueError(
                    "executable tournament branch must resolve to one registered intervention"
                )
            intervention_id = branch.intervention_ids[0]
            try:
                intervention = interventions_by_id[intervention_id]
            except KeyError as exc:
                raise ValueError("tournament branch references an unknown intervention") from exc
            requests.append(self.intervention_generator.compile_request(
                fixture,
                intervention,
                self._request_id(branch.branch_id),
                self._decision_id(branch.branch_id),
            ))

        return FailureResearchProgram(
            failure_snapshot_id=fixture.failure_snapshot_id,
            root_failure_snapshot_id=self._root_failure_id(fixture),
            fixture=fixture,
            autopsy=report,
            interventions=tuple(interventions),
            tournament=plan,
            replay_requests=tuple(requests),
            projected_physical_calls=plan.worst_case_physical_calls,
            model_calls=0,
        )

    def _validate_program(self, program: FailureResearchProgram) -> FailureFixture:
        if not isinstance(program, FailureResearchProgram):
            raise TypeError("program must be FailureResearchProgram")
        try:
            current = self.replay_store.get_failure(program.failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("program failure snapshot is not present") from exc
        if current != program.fixture:
            raise ValueError("program failure fixture drifted from canonical replay evidence")
        if self._root_failure_id(current) != program.root_failure_snapshot_id:
            raise ValueError("program root failure lineage drifted")
        for request in program.replay_requests:
            if request.parent_failure_snapshot_id != current.failure_snapshot_id:
                raise ValueError("program replay request parent failure drifted")
            if request.parent_state_hash != current.state_hash:
                raise ValueError("program replay request parent state drifted")
            if request.failure_snapshot_id != program.root_failure_snapshot_id:
                raise ValueError("program replay request root lineage drifted")
        return current

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
        program: FailureResearchProgram,
        adapters: Mapping[str, ReplayAdapter],
    ) -> FailureResearchResult:
        self._validate_program(program)
        if not isinstance(adapters, Mapping) or not adapters:
            raise ValueError("execute requires injected replay adapters")

        executor = ReplayExecutor(self.replay_store, adapters)
        results = tuple(executor.execute(request) for request in program.replay_requests)
        intervention_by_id = {
            item.intervention_id: item for item in program.interventions
        }
        target_results: list[ReplayResult] = []
        sham_results: list[ReplayResult] = []
        for request, result in zip(program.replay_requests, results, strict=True):
            intervention = intervention_by_id[request.intervention_id]
            if intervention.kind is InterventionKind.SHAM:
                sham_results.append(result)
            else:
                target_results.append(result)

        assessment = self.localizer.evaluate(program.root_failure_snapshot_id, results)
        child_ids = tuple(
            result.child_failure_snapshot_id
            for result in results
            if result.child_failure_snapshot_id is not None
        )
        return FailureResearchResult(
            program=program,
            replay_results=results,
            target_results=tuple(target_results),
            sham_results=tuple(sham_results),
            assessment=assessment,
            child_failure_snapshot_ids=child_ids,
            model_calls_are_fake_only=self._all_fake(adapters),
        )

    def ingest_child_failure(self, child_failure_snapshot_id: str) -> FailureResearchProgram:
        child = self.replay_store.get_failure(child_failure_snapshot_id)
        if child.parent_failure_snapshot_id is None:
            raise ValueError("ingest_child_failure requires a replay-derived child failure")
        return self.prepare(child_failure_snapshot_id)
