"""Compile Stage-6 mutation probes through the canonical replay path."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .causal_core import InterventionDefinition
from .causal_store import CausalEvidenceStore
from .core import (
    MechanismLabel,
    MutationFixture,
    MutationOrigin,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRequest,
    to_payload,
)
from .replay_store import ReplayStore, SupersessionRecord


def _scientific_payload(value: Any) -> dict[str, Any]:
    payload = to_payload(value)
    payload.pop("record_id", None)
    return payload


def _get_path(payload: Any, path: str) -> Any:
    current = payload
    for token in path.split("."):
        if isinstance(current, list):
            if not token.isdigit():
                raise ValueError(f"list replay dimension requires numeric index: {path}")
            index = int(token)
            if index < 0 or index >= len(current):
                raise ValueError(f"replay dimension index is out of range: {path}")
            current = current[index]
        elif isinstance(current, Mapping):
            if token not in current:
                raise ValueError(f"replay dimension does not exist: {path}")
            current = current[token]
        else:
            raise ValueError(f"replay dimension traverses non-container value: {path}")
    return current


def _transfer_leaf(source_value: Any, mutated_value: Any, proven_value: Any, *, path: str) -> Any:
    """Rebase a frozen repair delta without inventing mutation-specific tuning."""

    if mutated_value == source_value:
        return proven_value
    if isinstance(source_value, str) and isinstance(mutated_value, str) and isinstance(proven_value, str):
        if proven_value.startswith(source_value):
            return mutated_value + proven_value[len(source_value):]
    raise ValueError(
        f"proven repair overlaps mutated leaf without a deterministic rebase rule: {path}"
    )


class MutationReplayCompiler:
    """Apply an already-proven mechanism to a registered mutation fixture."""

    def __init__(self, replay_store: ReplayStore, causal_store: CausalEvidenceStore) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store

    def _active_record(self, record_type: type, logical_name: str, logical_id: str):
        records = self.replay_store.records()
        superseded = {
            record.old_record_id
            for record in records
            if isinstance(record, SupersessionRecord)
        }
        candidates = [
            record
            for record in records
            if isinstance(record, record_type)
            and getattr(record, logical_name) == logical_id
            and record.record_id not in superseded
        ]
        if len(candidates) != 1:
            raise ValueError(f"canonical {record_type.__name__} {logical_id!r} is not uniquely active")
        return candidates[0]

    def _canonical_mutation(self, mutation: MutationFixture) -> MutationFixture:
        if not isinstance(mutation, MutationFixture):
            raise TypeError("mutation_fixture must be MutationFixture")
        stored = self._active_record(
            MutationFixture, "mutation_fixture_id", mutation.mutation_fixture_id
        )
        if _scientific_payload(stored) != _scientific_payload(mutation):
            raise ValueError("mutation fixture differs from canonical replay evidence")
        return stored

    def _canonical_mechanism(self, mechanism: MechanismLabel) -> MechanismLabel:
        if not isinstance(mechanism, MechanismLabel):
            raise TypeError("mechanism_label must be MechanismLabel")
        stored = self._active_record(
            MechanismLabel, "mechanism_label_id", mechanism.mechanism_label_id
        )
        if _scientific_payload(stored) != _scientific_payload(mechanism):
            raise ValueError("mechanism label differs from canonical replay evidence")
        return stored

    def _require_movement(self, mechanism: MechanismLabel) -> None:
        movements = [
            record
            for record in self.replay_store.records()
            if isinstance(record, PromotionEvent)
            and record.failure_snapshot_id == mechanism.failure_snapshot_id
            and record.mechanism_id == mechanism.mechanism_id
            and record.to_state is PromotionState.MOVEMENT
        ]
        if not movements:
            raise ValueError("Stage-6 mutation replay requires canonical MOVEMENT evidence")

    def _execution_intervention(
        self,
        mechanism: MechanismLabel,
        intervention_ids: tuple[str, ...],
    ) -> InterventionDefinition:
        if tuple(intervention_ids) != mechanism.intervention_ids:
            raise ValueError("mechanism intervention IDs differ from the MOVEMENT mechanism")
        for intervention_id in intervention_ids:
            intervention = self.causal_store.get_intervention(intervention_id)
            if intervention.hypothesis_id != mechanism.hypothesis_id:
                raise ValueError("mechanism intervention hypothesis lineage mismatch")

        metadata = mechanism.metadata
        compound_id = metadata.get("compound_intervention_id") or metadata.get("ordered_compound")
        if compound_id is not None:
            if not isinstance(compound_id, str) or not compound_id.strip():
                raise ValueError("canonical compound intervention ID is invalid")
            compound = self.causal_store.get_intervention(compound_id)
            represented = tuple(dict.fromkeys(compound.composition))
            if not set(intervention_ids).issubset(set(represented)):
                raise ValueError("canonical compound does not contain the MOVEMENT mechanism components")
            return compound
        if len(intervention_ids) != 1:
            raise ValueError("multi-component mechanism lacks a canonical compound intervention")
        return self.causal_store.get_intervention(intervention_ids[0])

    def compile(
        self,
        mutation_fixture: MutationFixture,
        mechanism_label: MechanismLabel,
        intervention_ids: tuple[str, ...],
        *,
        request_id: str,
        decision_id: str = "D12",
    ) -> ReplayRequest:
        replay_validation = self.replay_store.validate()
        if not replay_validation.ok:
            raise ValueError("replay store integrity validation failed")
        causal_validation = self.causal_store.validate()
        if not causal_validation.ok:
            raise ValueError("causal evidence store integrity validation failed")
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id is required")
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise ValueError("decision_id is required")

        mutation = self._canonical_mutation(mutation_fixture)
        mechanism = self._canonical_mechanism(mechanism_label)
        self._require_movement(mechanism)
        if mutation.failure_snapshot_id != mechanism.failure_snapshot_id:
            raise ValueError("mutation and mechanism root failure lineage differ")
        if mutation.mechanism_id != mechanism.mechanism_id:
            raise ValueError("mutation fixture mechanism differs from MOVEMENT mechanism")
        if mutation.source_failure_snapshot_id != mechanism.parent_failure_snapshot_id:
            raise ValueError("mutation source failure differs from mechanism parent")
        if mutation.source_state_hash != mechanism.parent_state_hash:
            raise ValueError("mutation source state differs from mechanism parent state")

        try:
            source = self.replay_store.get_failure(mutation.source_failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("mutation source failure is missing") from exc
        if source.state_hash != mutation.source_state_hash or source.partition != mutation.partition:
            raise ValueError("mutation source state/partition differs from replay lineage")

        execution = self._execution_intervention(mechanism, tuple(intervention_ids))
        if execution.failure_snapshot_id != source.failure_snapshot_id:
            raise ValueError("execution intervention failure lineage differs from mutation source")
        if execution.parent_state_hash != source.state_hash:
            raise ValueError("execution intervention parent state differs from mutation source")
        if execution.projected_physical_calls == 0 or not execution.changed_dimensions:
            raise ValueError("Stage-6 transfer requires an executable model-visible repair")

        source_visible = self.replay_store.read_asset(source.model_visible_asset_sha256)
        mutation_visible = self.replay_store.read_asset(mutation.model_visible_asset_sha256)
        if not isinstance(source_visible, Mapping) or not isinstance(mutation_visible, Mapping):
            raise ValueError("source and mutation model-visible assets must be mappings")
        if not isinstance(mutation_visible.get("request_envelopes"), list):
            raise ValueError("mutation model-visible asset requires request_envelopes")

        overrides: dict[str, Any] = {}
        for path in execution.changed_dimensions:
            source_value = _get_path(source_visible, path)
            mutated_value = _get_path(mutation_visible, path)
            overrides[path] = _transfer_leaf(
                source_value,
                mutated_value,
                execution.overrides[path],
                path=path,
            )

        profile_id = mutation.metadata.get("operating_surface_profile_id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("mutation fixture requires operating_surface_profile_id provenance")

        return ReplayRequest(
            replay_request_id=request_id,
            failure_snapshot_id=mutation.failure_snapshot_id,
            parent_failure_snapshot_id=source.failure_snapshot_id,
            parent_state_hash=source.state_hash,
            decision_id=decision_id,
            hypothesis_id=mechanism.hypothesis_id,
            expected_causal_implication=(
                "test whether the already-proven repair mechanism transfers unchanged "
                "to the registered mutation fixture"
            ),
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=source.source_model_id,
            source_model_digest=source.source_model_digest,
            target_model_id=source.source_model_id,
            target_model_digest=source.source_model_digest,
            partition=source.partition,
            changed_dimensions=execution.changed_dimensions,
            intervention_id=execution.intervention_id,
            overrides=overrides,
            metadata={
                "mechanism_id": mechanism.mechanism_id,
                "mechanism_label_id": mechanism.mechanism_label_id,
                "mechanism_intervention_ids": mechanism.intervention_ids,
                "execution_intervention_id": execution.intervention_id,
                "mutation_fixture_id": mutation.mutation_fixture_id,
                "mutation_axis": mutation.mutation_axis.value,
                "mutation_direction": mutation.mutation_direction.value,
                "structural_region_id": mutation.structural_region_id,
                "synthetic_neighborhood": (
                    mutation.origin is MutationOrigin.SYNTHETIC_NEIGHBORHOOD
                ),
                "operating_surface_profile_id": profile_id,
            },
        )
