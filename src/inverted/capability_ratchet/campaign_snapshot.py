"""Live campaign failure snapshots backed by the canonical TEST_REPLAY store."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from .core import FailureFixture, Partition, _json_value
from .orchestration import AttemptContext, AttemptEvidence, AttemptOutcome
from .replay_store import ReplayStore
from .snapshot import _canonical, _json_copy, _scan_secrets


class ReplayFailureSnapshotter:
    """Persist each failed campaign attempt as an immutable replay fixture.

    V3 campaign snapshots deliberately keep three independent content-addressed
    assets: exact model-visible state, forensic/raw attempt evidence, and
    oracle/scoring material. Retry lineage is tracked per model/task and resets
    on each INITIAL attempt so separate campaign runs cannot cross-link.
    """

    def __init__(
        self,
        *,
        store: ReplayStore,
        source_campaign_id: str,
        runtime_provenance: Mapping[str, Any],
        partition: Partition,
    ) -> None:
        if not isinstance(store, ReplayStore):
            raise TypeError("store must be a ReplayStore")
        if not isinstance(source_campaign_id, str) or not source_campaign_id.strip():
            raise ValueError("source_campaign_id is required")
        runtime = _json_copy(runtime_provenance, name="runtime_provenance")
        model = runtime.get("model")
        digest = runtime.get("model_digest")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("runtime_provenance requires model")
        if not isinstance(digest, str) or not digest.strip():
            raise ValueError("runtime_provenance requires model_digest")
        _scan_secrets(runtime, label="runtime_provenance")

        self._store = store
        self._source_campaign_id = source_campaign_id
        self._runtime = runtime
        self._partition = partition if isinstance(partition, Partition) else Partition(partition)
        self._parents: dict[tuple[str, str], tuple[str, str]] = {}

    @staticmethod
    def _plain(value: Any, *, name: str) -> Any:
        return _json_copy(_json_value(value), name=name)

    def __call__(self, context: AttemptContext, outcome: AttemptOutcome) -> str:
        if not isinstance(context, AttemptContext):
            raise TypeError("context must be AttemptContext")
        if not isinstance(outcome, AttemptOutcome):
            raise TypeError("outcome must be AttemptOutcome")
        if outcome.passed:
            raise ValueError("only failed attempts may be snapshotted")
        if not isinstance(outcome.evidence, AttemptEvidence):
            raise ValueError("failed replay snapshots require AttemptEvidence")
        if context.model_id != self._runtime["model"]:
            raise ValueError("attempt model does not match runtime provenance")

        evidence = outcome.evidence
        visible = {
            "request_envelopes": self._plain(
                evidence.request_envelopes, name="request_envelopes"
            )
        }
        forensic = self._plain(evidence.forensic_payload, name="forensic_payload")
        oracle = self._plain(evidence.oracle_payload, name="oracle_payload")
        profile = self._plain(evidence.inference_profile, name="inference_profile")
        retry = context.retry_ingredient
        retry_intervention = (
            None
            if retry is None
            else self._plain(retry.to_payload(), name="retry_intervention")
        )

        for label, payload in (
            ("model_visible", visible),
            ("forensic", forensic),
            ("oracle", oracle),
            ("inference_profile", profile),
            ("retry_intervention", retry_intervention),
        ):
            if payload is not None:
                _scan_secrets(payload, label=label)

        visible_sha = self._store.put_asset(visible)
        forensic_sha = self._store.put_asset(forensic)
        oracle_sha = self._store.put_asset(oracle)

        parent_key = (context.model_id, context.task.task_id)
        if context.stage == "INITIAL":
            self._parents.pop(parent_key, None)
            parent_id = None
            parent_hash = None
        else:
            parent = self._parents.get(parent_key)
            if parent is None:
                raise ValueError("retry snapshot requires the preceding failed attempt")
            parent_id, parent_hash = parent

        identity = {
            "source_campaign_id": self._source_campaign_id,
            "model_id": context.model_id,
            "model_digest": self._runtime["model_digest"],
            "task_id": context.task.task_id,
            "attempt_stage": context.stage,
            "attempt_index": context.attempt_index,
            "retry_ingredient_id": None if retry is None else retry.ingredient_id,
            "retry_intervention": retry_intervention,
            "state_hash": visible_sha,
            "failure_classes": list(outcome.failure_classes),
            "failure_subtypes": list(outcome.failure_subtypes),
        }
        failure_snapshot_id = (
            "test1b-v3-" + hashlib.sha256(_canonical(identity)).hexdigest()[:24]
        )
        source_trial_id = (
            f"{self._source_campaign_id}:{context.model_id}:"
            f"{context.task.task_id}:{context.stage}"
        )
        refs = tuple(evidence.source_evidence_refs) + (
            f"forensic-asset:{forensic_sha}",
            f"oracle-asset:{oracle_sha}",
        )
        fixture = FailureFixture(
            failure_snapshot_id=failure_snapshot_id,
            source_campaign_id=self._source_campaign_id,
            source_trial_id=source_trial_id,
            focus_observation_id=f"{source_trial_id}:attempt:{context.attempt_index}",
            focus_task_id=context.task.task_id,
            batch_task_ids=(context.task.task_id,),
            family=context.task.family,
            failure_classes=outcome.failure_classes,
            source_model_id=context.model_id,
            source_model_digest=self._runtime["model_digest"],
            source_runtime=self._runtime,
            inference_profile=profile,
            inference_seed=evidence.inference_seed,
            partition=self._partition,
            model_visible_asset_sha256=visible_sha,
            state_hash=visible_sha,
            oracle_ref=f"replay-asset-sha256:{oracle_sha}",
            expected_contract=context.task.contract,
            source_evidence_refs=refs,
            metadata={
                "difficulty": context.task.difficulty,
                "scorer": context.task.scorer,
                "attempt_stage": context.stage,
                "attempt_index": context.attempt_index,
                "retry_ingredient_id": None if retry is None else retry.ingredient_id,
                "retry_ingredient_description": None if retry is None else retry.description,
                "retry_intervention": retry_intervention,
                "failure_subtypes": outcome.failure_subtypes,
                "forensic_asset_sha256": forensic_sha,
                "oracle_asset_sha256": oracle_sha,
                "lineage_kind": "CAMPAIGN_RETRY",
            },
            parent_failure_snapshot_id=parent_id,
            parent_state_hash=parent_hash,
        )
        self._store.append(fixture)
        self._parents[parent_key] = (fixture.failure_snapshot_id, fixture.state_hash)
        return fixture.failure_snapshot_id
