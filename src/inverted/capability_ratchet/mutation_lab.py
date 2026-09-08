"""Adaptive Stage-6 mutation orchestration over the canonical replay kernel."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .causal_store import CausalEvidenceStore
from .core import MechanismLabel, MutationFixture, ReplayResult
from .mutation_analysis import MutationAnalyzer
from .mutation_generator import MutationGenerator, MutationTemplate
from .mutation_planner import MutationPlan, MutationPlanner
from .mutation_replay import MutationReplayCompiler
from .mutation_store import MutationEvidenceStore, MutationOutcome, MutationStudy
from .replay import ReplayAdapter, ReplayExecutor
from .replay_store import ReplayStore


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class MutationStepResult:
    plan: MutationPlan
    replay_results: tuple[ReplayResult, ...]
    outcomes: tuple[MutationOutcome, ...]
    profile: Any
    promotion_event: Any | None
    next_plan: MutationPlan
    child_failure_snapshot_ids: tuple[str, ...]
    model_calls_are_fake_only: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_results", tuple(self.replay_results))
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        object.__setattr__(self, "child_failure_snapshot_ids", tuple(self.child_failure_snapshot_ids))
        if type(self.model_calls_are_fake_only) is not bool:
            raise TypeError("model_calls_are_fake_only must be boolean")


class MutationLab:
    """Materialize and execute one bounded Stage-6 neighborhood step.

    Templates are injected explicit scientific objects. This class never infers a
    mutation template and never constructs a model transport. All execution is
    delegated to the canonical :class:`ReplayExecutor`.
    """

    def __init__(
        self,
        replay_store: ReplayStore,
        causal_store: CausalEvidenceStore,
        mutation_store: MutationEvidenceStore,
        *,
        templates: Mapping[str, MutationTemplate],
        generator: MutationGenerator,
        planner: MutationPlanner,
        replay_compiler: MutationReplayCompiler,
        analyzer: MutationAnalyzer,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        if not isinstance(mutation_store, MutationEvidenceStore):
            raise TypeError("mutation_store must be MutationEvidenceStore")
        if not isinstance(templates, Mapping):
            raise TypeError("templates must be a mapping")
        if not isinstance(generator, MutationGenerator):
            raise TypeError("generator must be MutationGenerator")
        if not isinstance(planner, MutationPlanner):
            raise TypeError("planner must be MutationPlanner")
        if not isinstance(replay_compiler, MutationReplayCompiler):
            raise TypeError("replay_compiler must be MutationReplayCompiler")
        if not isinstance(analyzer, MutationAnalyzer):
            raise TypeError("analyzer must be MutationAnalyzer")
        if mutation_store.replay_store is not replay_store:
            raise ValueError("mutation store must use the canonical replay store")
        self.replay_store = replay_store
        self.causal_store = causal_store
        self.mutation_store = mutation_store
        self.templates = dict(templates)
        self.generator = generator
        self.planner = planner
        self.replay_compiler = replay_compiler
        self.analyzer = analyzer

    def _validate_stores(self) -> None:
        if not self.replay_store.validate().ok:
            raise ValueError("replay store integrity validation failed")
        if not self.causal_store.validate().ok:
            raise ValueError("causal evidence store integrity validation failed")
        if not self.mutation_store.validate().ok:
            raise ValueError("mutation evidence store integrity validation failed")

    def _study(self, study_id: str) -> MutationStudy:
        if not isinstance(study_id, str) or not study_id.strip():
            raise ValueError("study_id is required")
        matches = tuple(item for item in self.mutation_store.studies() if item.study_id == study_id)
        if len(matches) != 1:
            raise ValueError("mutation study must resolve to exactly one stored study")
        return matches[0]

    def _fixture_for_spec(self, study: MutationStudy, spec_id: str) -> MutationFixture | None:
        rows = tuple(
            row
            for row in self.replay_store.records()
            if isinstance(row, MutationFixture)
            and row.failure_snapshot_id == study.failure_snapshot_id
            and row.mechanism_id == study.mechanism_id
            and row.source_failure_snapshot_id == study.source_failure_snapshot_id
            and row.source_state_hash == study.source_state_hash
            and row.metadata.get("mutation_spec_id") == spec_id
        )
        logical_ids = {row.mutation_fixture_id for row in rows}
        if len(logical_ids) > 1:
            raise ValueError("mutation spec maps to multiple canonical fixture identities")
        return rows[-1] if rows else None

    def _template(self, study: MutationStudy, structural_region_id: str) -> MutationTemplate:
        raw = self.templates.get(study.study_id)
        if raw is None:
            raw = self.templates.get(structural_region_id)
        if not isinstance(raw, MutationTemplate):
            raise ValueError(
                f"NO_MUTATION_TEMPLATE: study {study.study_id} region {structural_region_id} has no explicit template"
            )
        if raw.source_failure_snapshot_id != study.source_failure_snapshot_id:
            raise ValueError("mutation template source failure differs from study")
        if raw.structural_region_id != structural_region_id:
            raise ValueError("mutation template structural region differs from selected spec")
        if raw.operator_state.get("mechanism_id") != study.mechanism_id:
            raise ValueError("mutation template mechanism differs from study")
        metadata = dict(raw.metadata)
        if study.operating_surface_profile_id is not None:
            metadata["operating_surface_profile_id"] = study.operating_surface_profile_id
        return replace(raw, metadata=metadata)

    def prepare(self, study_id: str, *, max_new_mutations: int = 3) -> MutationPlan:
        self._validate_stores()
        study = self._study(study_id)
        plan = self.planner.plan_next(study, max_new_mutations=max_new_mutations)
        for spec in plan.specs:
            if self._fixture_for_spec(study, spec.spec_id) is not None:
                continue
            template = self._template(study, spec.structural_region_id)
            fixture = self.generator.generate(template, spec)
            if fixture.failure_snapshot_id != study.failure_snapshot_id:
                raise ValueError("generated mutation root lineage differs from study")
            if fixture.mechanism_id != study.mechanism_id:
                raise ValueError("generated mutation mechanism differs from study")
        self._validate_stores()
        return plan

    def _study_for_plan(self, plan: MutationPlan) -> MutationStudy:
        if not plan.specs:
            raise ValueError("stopped mutation plan has no executable specs")
        wanted = {item.spec_id for item in plan.specs}
        candidates = []
        for study in self.mutation_store.studies():
            registered = {item.spec_id for item in study.candidate_specs}
            if not wanted.issubset(registered):
                continue
            if all(self._fixture_for_spec(study, spec_id) is not None for spec_id in wanted):
                candidates.append(study)
        if len(candidates) != 1:
            raise ValueError("mutation plan must resolve to exactly one materialized study")
        return candidates[0]

    def _mechanism(self, study: MutationStudy) -> MechanismLabel:
        rows = tuple(
            row
            for row in self.replay_store.records()
            if isinstance(row, MechanismLabel)
            and row.failure_snapshot_id == study.failure_snapshot_id
            and row.mechanism_id == study.mechanism_id
        )
        ids = {row.mechanism_label_id for row in rows}
        if len(ids) != 1:
            raise ValueError("mutation study mechanism must resolve to one canonical mechanism label")
        return rows[-1]

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
    def _request_id(study: MutationStudy, fixture: MutationFixture) -> str:
        return f"mutation-replay-{study.study_id}-{fixture.mutation_fixture_id}"

    @staticmethod
    def _outcome_id(study: MutationStudy, fixture: MutationFixture, result: ReplayResult) -> str:
        payload = {
            "study_id": study.study_id,
            "mutation_fixture_id": fixture.mutation_fixture_id,
            "replay_result_id": result.replay_result_id,
        }
        return f"mutation-outcome-{hashlib.sha256(_canonical(payload)).hexdigest()[:24]}"

    def execute(
        self,
        plan: MutationPlan,
        adapters: Mapping[str, ReplayAdapter],
    ) -> MutationStepResult:
        if not isinstance(plan, MutationPlan):
            raise TypeError("plan must be MutationPlan")
        if plan.stop_reason is not None or not plan.specs:
            raise ValueError("stopped mutation plan has no executable specs")
        if not isinstance(adapters, Mapping) or not adapters:
            raise ValueError("execute requires injected replay adapters")
        self._validate_stores()
        study = self._study_for_plan(plan)
        mechanism = self._mechanism(study)

        fixtures = tuple(
            self._fixture_for_spec(study, spec.spec_id)
            for spec in plan.specs
        )
        if any(fixture is None for fixture in fixtures):
            raise ValueError("mutation plan has an unmaterialized fixture")
        concrete = tuple(fixture for fixture in fixtures if fixture is not None)
        requests = tuple(
            self.replay_compiler.compile(
                fixture,
                mechanism,
                mechanism.intervention_ids,
                request_id=self._request_id(study, fixture),
                decision_id=study.decision_id,
            )
            for fixture in concrete
        )
        executor = ReplayExecutor(self.replay_store, adapters)
        results = tuple(executor.execute(request) for request in requests)

        outcomes = []
        for fixture, result in zip(concrete, results, strict=True):
            outcome = MutationOutcome(
                outcome_id=self._outcome_id(study, fixture, result),
                study_id=study.study_id,
                mutation_fixture_id=fixture.mutation_fixture_id,
                replay_result_id=result.replay_result_id,
                axis=fixture.mutation_axis,
                direction=fixture.mutation_direction,
                structural_region_id=fixture.structural_region_id,
                protected=bool(fixture.metadata.get("protected", False)),
                semantic_pass=result.semantic_pass,
                contract_pass=result.contract_pass,
                metadata={
                    "completed": result.completed,
                    "child_failure_snapshot_id": result.child_failure_snapshot_id,
                },
            )
            self.mutation_store.append_outcome(outcome)
            outcomes.append(outcome)

        profile = self.analyzer.analyze(study.study_id)
        promotion = self.analyzer.maybe_promote(profile)
        next_plan = self.planner.plan_next(study)
        child_ids = tuple(
            result.child_failure_snapshot_id
            for result in results
            if result.child_failure_snapshot_id is not None
        )
        self._validate_stores()
        return MutationStepResult(
            plan=plan,
            replay_results=results,
            outcomes=tuple(outcomes),
            profile=profile,
            promotion_event=promotion,
            next_plan=next_plan,
            child_failure_snapshot_ids=child_ids,
            model_calls_are_fake_only=self._all_fake(adapters),
        )
