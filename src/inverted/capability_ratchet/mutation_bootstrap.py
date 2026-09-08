"""Zero-call Stage-6 eligibility discovery from canonical MOVEMENT evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .core import MechanismLabel, Partition, PromotionEvent, PromotionState
from .mutation_planner import MutationPlan, MutationPlanner
from .mutation_store import MutationEvidenceStore, MutationStudy


@dataclass(frozen=True)
class MutationBootstrapPlan:
    study: MutationStudy
    plan: MutationPlan


@dataclass(frozen=True)
class MutationBootstrapResult:
    status: str
    eligible_mechanisms: tuple[str, ...]
    plans: tuple[MutationBootstrapPlan, ...]

    def __post_init__(self) -> None:
        if self.status not in {
            "NO_ELIGIBLE_MECHANISMS",
            "NO_MUTATION_TEMPLATE",
            "MUTATION_PLAN_READY",
        }:
            raise ValueError("unsupported Stage-6 bootstrap status")
        object.__setattr__(self, "eligible_mechanisms", tuple(self.eligible_mechanisms))
        object.__setattr__(self, "plans", tuple(self.plans))

    @property
    def model_calls(self) -> int:
        return 0


def _current_state(
    mutation_store: MutationEvidenceStore,
    failure_snapshot_id: str,
    mechanism_id: str,
) -> PromotionState:
    replay_store = mutation_store.replay_store
    current = replay_store.get_failure(failure_snapshot_id).promotion_state
    for record in replay_store.records():
        if not isinstance(record, PromotionEvent):
            continue
        if (
            record.failure_snapshot_id != failure_snapshot_id
            or record.mechanism_id != mechanism_id
        ):
            continue
        if record.from_state is not current:
            raise ValueError("promotion event chain is not contiguous for mechanism")
        current = record.to_state
    return current


def _eligible_keys(
    mutation_store: MutationEvidenceStore,
) -> tuple[tuple[str, str], ...]:
    replay_store = mutation_store.replay_store
    keys = {
        (record.failure_snapshot_id, record.mechanism_id)
        for record in replay_store.records()
        if isinstance(record, MechanismLabel)
    }
    eligible: list[tuple[str, str]] = []
    for failure_snapshot_id, mechanism_id in sorted(keys):
        fixture = replay_store.get_failure(failure_snapshot_id)
        if fixture.partition in {Partition.FRESH, Partition.SEALED}:
            continue
        if _current_state(mutation_store, failure_snapshot_id, mechanism_id) is PromotionState.MOVEMENT:
            eligible.append((failure_snapshot_id, mechanism_id))
    return tuple(eligible)


def plan_eligible_mutations(
    mutation_store: MutationEvidenceStore,
    *,
    max_new_mutations: int = 3,
) -> MutationBootstrapResult:
    """Plan registered Stage-6 neighborhoods without inventing templates or making calls.

    The bootstrap is intentionally conservative. Canonical MOVEMENT is the entry
    prerequisite. If MOVEMENT exists but no registered Stage-6 study exists for
    that failure/mechanism pair, the result is ``NO_MUTATION_TEMPLATE`` rather
    than manufacturing mutation geometry from historical evidence.
    """

    if not isinstance(mutation_store, MutationEvidenceStore):
        raise TypeError("mutation_store must be MutationEvidenceStore")
    validation = mutation_store.validate()
    if not validation.ok:
        raise ValueError("mutation evidence store integrity validation failed")
    if (
        not isinstance(max_new_mutations, int)
        or isinstance(max_new_mutations, bool)
        or max_new_mutations < 1
    ):
        raise ValueError("max_new_mutations must be a positive integer")

    eligible = _eligible_keys(mutation_store)
    mechanism_ids = tuple(sorted({mechanism_id for _, mechanism_id in eligible}))
    if not eligible:
        return MutationBootstrapResult(
            status="NO_ELIGIBLE_MECHANISMS",
            eligible_mechanisms=(),
            plans=(),
        )

    planner = MutationPlanner(mutation_store)
    plans: list[MutationBootstrapPlan] = []
    for failure_snapshot_id, mechanism_id in eligible:
        studies = tuple(
            study
            for study in mutation_store.studies(mechanism_id)
            if study.failure_snapshot_id == failure_snapshot_id
        )
        for study in studies:
            plans.append(
                MutationBootstrapPlan(
                    study=study,
                    plan=planner.plan_next(
                        study,
                        max_new_mutations=max_new_mutations,
                    ),
                )
            )

    if not plans:
        return MutationBootstrapResult(
            status="NO_MUTATION_TEMPLATE",
            eligible_mechanisms=mechanism_ids,
            plans=(),
        )
    return MutationBootstrapResult(
        status="MUTATION_PLAN_READY",
        eligible_mechanisms=mechanism_ids,
        plans=tuple(plans),
    )
