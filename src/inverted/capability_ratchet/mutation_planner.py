"""Deterministic, bounded planning for Stage-6 mutation neighborhoods."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .core import MutationFixture
from .mutation_core import (
    GeneralizationClass,
    GeneralizationProfile,
    MutationDirection,
    MutationSpec,
)
from .mutation_store import MutationOutcome, MutationStudy


_CLASS_RANK = {
    GeneralizationClass.INSTANCE_PATCH: 0,
    GeneralizationClass.LOCAL_MECHANISM: 1,
    GeneralizationClass.REGION_MECHANISM: 2,
    GeneralizationClass.CROSS_REGION_MECHANISM: 3,
    GeneralizationClass.PROMOTION_CANDIDATE: 4,
}


@dataclass(frozen=True)
class MutationPlan:
    specs: tuple[MutationSpec, ...]
    reused_fixture_ids: tuple[str, ...]
    decision_reason: str
    minimum_physical_calls: int
    expected_physical_calls: int
    worst_case_physical_calls: int
    protected_challenge_calls: int
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "specs", tuple(self.specs))
        object.__setattr__(self, "reused_fixture_ids", tuple(self.reused_fixture_ids))
        if not isinstance(self.decision_reason, str) or not self.decision_reason.strip():
            raise ValueError("decision_reason is required")
        counts = (
            self.minimum_physical_calls,
            self.expected_physical_calls,
            self.worst_case_physical_calls,
            self.protected_challenge_calls,
        )
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            for value in counts
        ):
            raise ValueError("mutation plan call counts must be non-negative integers")
        if not self.minimum_physical_calls <= self.expected_physical_calls <= self.worst_case_physical_calls:
            raise ValueError("mutation plan call counts must be ordered")
        if self.protected_challenge_calls > self.worst_case_physical_calls:
            raise ValueError("protected challenge calls cannot exceed worst-case calls")
        spec_ids = tuple(item.spec_id for item in self.specs)
        if len(set(spec_ids)) != len(spec_ids):
            raise ValueError("mutation plan specs must be unique")
        if len(set(self.reused_fixture_ids)) != len(self.reused_fixture_ids):
            raise ValueError("reused fixture IDs must be unique")
        if self.stop_reason is not None and self.specs:
            raise ValueError("stopped mutation plans cannot contain executable specs")


class MutationPlanner:
    """Choose only the next mutation probes capable of changing Stage-6 decisions."""

    def __init__(self, mutation_store: Any) -> None:
        if not callable(getattr(mutation_store, "outcomes", None)):
            raise TypeError("mutation_store must expose outcomes()")
        if not callable(getattr(mutation_store, "profiles", None)):
            raise TypeError("mutation_store must expose profiles()")
        replay_store = getattr(mutation_store, "replay_store", None)
        if replay_store is None or not callable(getattr(replay_store, "records", None)):
            raise TypeError("mutation_store must expose replay_store.records()")
        self.mutation_store = mutation_store

    def _answered(self, study: MutationStudy) -> tuple[frozenset[str], tuple[str, ...]]:
        fixture_by_id = {
            record.mutation_fixture_id: record
            for record in self.mutation_store.replay_store.records()
            if isinstance(record, MutationFixture)
            and record.failure_snapshot_id == study.failure_snapshot_id
            and record.mechanism_id == study.mechanism_id
            and record.source_failure_snapshot_id == study.source_failure_snapshot_id
            and record.source_state_hash == study.source_state_hash
        }
        candidate_ids = {item.spec_id for item in study.candidate_specs}
        answered_specs: set[str] = set()
        reused: list[str] = []
        for outcome in self.mutation_store.outcomes(study.study_id):
            if not isinstance(outcome, MutationOutcome):
                continue
            fixture = fixture_by_id.get(outcome.mutation_fixture_id)
            if fixture is None:
                continue
            spec_id = fixture.metadata.get("mutation_spec_id")
            if isinstance(spec_id, str) and spec_id in candidate_ids:
                answered_specs.add(spec_id)
                if fixture.mutation_fixture_id not in reused:
                    reused.append(fixture.mutation_fixture_id)
        return frozenset(answered_specs), tuple(reused)

    def _latest_profile(self, study: MutationStudy) -> GeneralizationProfile | None:
        rows = tuple(
            profile
            for profile in self.mutation_store.profiles(study.study_id)
            if isinstance(profile, GeneralizationProfile)
            and profile.failure_snapshot_id == study.failure_snapshot_id
            and profile.mechanism_id == study.mechanism_id
        )
        return rows[-1] if rows else None

    @staticmethod
    def _optimistic_classification(
        profile: GeneralizationProfile,
        unresolved: tuple[MutationSpec, ...],
    ) -> GeneralizationClass:
        policy = profile.policy
        current_axis = {key: int(value) for key, value in profile.axis_successes.items()}
        current_region = {key: int(value) for key, value in profile.region_successes.items()}
        for item in unresolved:
            current_axis[item.axis.value] = current_axis.get(item.axis.value, 0) + 1
            current_region[item.structural_region_id] = current_region.get(item.structural_region_id, 0) + 1

        successes = sum(current_axis.values())
        axes = sum(1 for value in current_axis.values() if value > 0)
        regions = sum(1 for value in current_region.values() if value > 0)
        harder = profile.harder_successes + sum(
            1 for item in unresolved if item.direction is MutationDirection.HARDER
        )

        existing_successes = sum(int(value) for value in profile.axis_successes.values())
        if existing_successes <= 0:
            estimated_existing_trials = 0
        elif profile.success_rate <= 0.0:
            estimated_existing_trials = existing_successes
        else:
            estimated_existing_trials = max(
                existing_successes,
                int(math.ceil(existing_successes / profile.success_rate)),
            )
        optimistic_rate = (
            (existing_successes + len(unresolved))
            / (estimated_existing_trials + len(unresolved))
            if estimated_existing_trials + len(unresolved)
            else 0.0
        )

        if (
            successes >= policy.min_promotion_successes
            and axes >= policy.min_promotion_axes
            and harder >= policy.min_harder_successes
            and optimistic_rate >= policy.min_success_rate
            and not profile.protected_failures
        ):
            return GeneralizationClass.PROMOTION_CANDIDATE
        if (
            successes >= policy.min_cross_region_successes
            and regions >= policy.min_cross_regions
        ):
            return GeneralizationClass.CROSS_REGION_MECHANISM
        if successes >= policy.min_region_successes and axes >= policy.min_region_axes:
            return GeneralizationClass.REGION_MECHANISM
        if any(value >= policy.min_local_successes for value in current_axis.values()):
            return GeneralizationClass.LOCAL_MECHANISM
        return GeneralizationClass.INSTANCE_PATCH

    @staticmethod
    def _select_diverse(
        unresolved: tuple[MutationSpec, ...],
        max_new_mutations: int,
    ) -> tuple[MutationSpec, ...]:
        if not unresolved:
            return ()

        selected: list[MutationSpec] = []
        represented_axes = set()

        protected = tuple(item for item in unresolved if item.protected)
        protected_harder = tuple(
            item for item in protected if item.direction is MutationDirection.HARDER
        )
        mandatory = protected_harder[0] if protected_harder else (protected[0] if protected else None)
        if mandatory is not None:
            selected.append(mandatory)
            represented_axes.add(mandatory.axis)

        for item in unresolved:
            if len(selected) >= max_new_mutations:
                break
            if item in selected or item.axis in represented_axes:
                continue
            selected.append(item)
            represented_axes.add(item.axis)

        harder_exists = any(item.direction is MutationDirection.HARDER for item in unresolved)
        harder_selected = any(item.direction is MutationDirection.HARDER for item in selected)
        if harder_exists and not harder_selected and selected:
            harder = next(item for item in unresolved if item.direction is MutationDirection.HARDER)
            if len(selected) < max_new_mutations:
                selected.append(harder)
            else:
                replace_index = next(
                    (index for index in range(len(selected) - 1, -1, -1) if not selected[index].protected),
                    len(selected) - 1,
                )
                selected[replace_index] = harder

        for item in unresolved:
            if len(selected) >= max_new_mutations:
                break
            if item not in selected:
                selected.append(item)

        return tuple(selected[:max_new_mutations])

    @staticmethod
    def _reason(specs: tuple[MutationSpec, ...]) -> str:
        clauses = []
        for item in specs:
            challenge = "protected challenge" if item.protected else "decision probe"
            clauses.append(
                f"{item.spec_id}: {challenge} on {item.axis.value}/{item.direction.value} can move "
                "the D12 classification or expose a neighborhood boundary"
            )
        return "; ".join(clauses)

    @staticmethod
    def _stopped(
        *,
        reused: tuple[str, ...],
        reason: str,
    ) -> MutationPlan:
        return MutationPlan(
            specs=(),
            reused_fixture_ids=reused,
            decision_reason=reason,
            minimum_physical_calls=0,
            expected_physical_calls=0,
            worst_case_physical_calls=0,
            protected_challenge_calls=0,
            stop_reason=reason,
        )

    def plan_next(self, study: MutationStudy, *, max_new_mutations: int = 3) -> MutationPlan:
        if not isinstance(study, MutationStudy):
            raise TypeError("study must be MutationStudy")
        if (
            not isinstance(max_new_mutations, int)
            or isinstance(max_new_mutations, bool)
            or max_new_mutations < 1
        ):
            raise ValueError("max_new_mutations must be a positive integer")

        answered, reused = self._answered(study)
        unresolved = tuple(
            item for item in study.candidate_specs if item.spec_id not in answered
        )
        current = self._latest_profile(study)

        if not unresolved:
            return self._stopped(
                reused=reused,
                reason="all registered mutation candidates are already answered; D12 is settled for this neighborhood",
            )

        if current is not None:
            if current.classification is GeneralizationClass.PROMOTION_CANDIDATE:
                return self._stopped(
                    reused=reused,
                    reason="mutation evidence already reaches PROMOTION_CANDIDATE; no further Stage-6 probe can move D12",
                )
            if current.protected_failures:
                return self._stopped(
                    reused=reused,
                    reason="protected mutation failure is an absolute Stage-6 promotion veto; additional averaging is forbidden",
                )
            optimistic = self._optimistic_classification(current, unresolved)
            if _CLASS_RANK[optimistic] <= _CLASS_RANK[current.classification]:
                return self._stopped(
                    reused=reused,
                    reason=(
                        f"remaining admissible mutations cannot move current classification "
                        f"{current.classification.value}; D12 is settled at this evidence boundary"
                    ),
                )

        selected = self._select_diverse(unresolved, max_new_mutations)
        selected_calls = len(selected)
        return MutationPlan(
            specs=selected,
            reused_fixture_ids=reused,
            decision_reason=self._reason(selected),
            minimum_physical_calls=selected_calls,
            expected_physical_calls=selected_calls,
            worst_case_physical_calls=len(unresolved),
            protected_challenge_calls=sum(1 for item in selected if item.protected),
        )