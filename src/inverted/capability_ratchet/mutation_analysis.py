"""Deterministic Stage-6 generalization classification and promotion gating."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from .core import FailureFixture, PromotionEvent, PromotionState, ReplayResult
from .mutation_core import GeneralizationClass, GeneralizationProfile, MutationDirection
from .mutation_store import MutationEvidenceStore, MutationOutcome, MutationStudy
from .replay_store import ReplayStore


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _success(outcome: MutationOutcome) -> bool:
    return bool(outcome.semantic_pass and outcome.contract_pass)


class MutationAnalyzer:
    """Classify registered mutation evidence under the study's persisted policy."""

    def __init__(self, replay_store: ReplayStore, mutation_store: MutationEvidenceStore) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(mutation_store, MutationEvidenceStore):
            raise TypeError("mutation_store must be MutationEvidenceStore")
        if mutation_store.replay_store is not replay_store:
            raise ValueError("mutation_store must reference the same canonical replay store")
        self.replay_store = replay_store
        self.mutation_store = mutation_store

    def _study(self, study_id: str) -> MutationStudy:
        if not isinstance(study_id, str) or not study_id.strip():
            raise ValueError("study_id must be non-blank")
        matches = tuple(item for item in self.mutation_store.studies() if item.study_id == study_id)
        if len(matches) != 1:
            raise ValueError("mutation study must resolve uniquely")
        return matches[0]

    @staticmethod
    def _classification(
        study: MutationStudy,
        outcomes: tuple[MutationOutcome, ...],
    ) -> tuple[
        GeneralizationClass,
        dict[str, int],
        dict[str, int],
        int,
        float,
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
    ]:
        policy = study.policy
        successful = tuple(item for item in outcomes if _success(item))
        failed = tuple(item for item in outcomes if not _success(item))
        axis_counts = Counter(item.axis.value for item in successful)
        region_counts = Counter(item.structural_region_id for item in successful)
        harder_successes = sum(
            1 for item in successful if item.direction is MutationDirection.HARDER
        )
        success_rate = (len(successful) / len(outcomes)) if outcomes else 0.0
        protected_failures = tuple(
            sorted(item.mutation_fixture_id for item in failed if item.protected)
        )
        boundaries = tuple(sorted(
            (
                f"{item.axis.value}:{item.direction.value}:{item.structural_region_id}:"
                f"NEGATIVE_TRANSFER:{item.mutation_fixture_id}"
            )
            for item in failed
        ))

        promotion_ready = (
            len(successful) >= policy.min_promotion_successes
            and len(axis_counts) >= policy.min_promotion_axes
            and harder_successes >= policy.min_harder_successes
            and success_rate >= policy.min_success_rate
            and not protected_failures
        )
        cross_region = (
            len(successful) >= policy.min_cross_region_successes
            and len(region_counts) >= policy.min_cross_regions
        )
        region = (
            len(successful) >= policy.min_region_successes
            and len(axis_counts) >= policy.min_region_axes
        )
        local = (
            len(successful) >= policy.min_local_successes
            and any(count >= policy.min_local_successes for count in axis_counts.values())
        )

        if promotion_ready:
            classification = GeneralizationClass.PROMOTION_CANDIDATE
        elif cross_region:
            classification = GeneralizationClass.CROSS_REGION_MECHANISM
        elif region:
            classification = GeneralizationClass.REGION_MECHANISM
        elif local:
            classification = GeneralizationClass.LOCAL_MECHANISM
        else:
            classification = GeneralizationClass.INSTANCE_PATCH

        return (
            classification,
            dict(sorted(axis_counts.items())),
            dict(sorted(region_counts.items())),
            harder_successes,
            success_rate,
            protected_failures,
            boundaries,
            tuple(sorted(item.mutation_fixture_id for item in successful)),
            tuple(sorted(item.mutation_fixture_id for item in failed)),
        )

    def analyze(self, study_id: str) -> GeneralizationProfile:
        validation = self.mutation_store.validate()
        if not validation.ok:
            raise ValueError("mutation evidence store integrity validation failed")
        study = self._study(study_id)
        outcomes = tuple(sorted(self.mutation_store.outcomes(study.study_id), key=lambda item: item.outcome_id))
        (
            classification,
            axis_successes,
            region_successes,
            harder_successes,
            success_rate,
            protected_failures,
            boundaries,
            successful_fixture_ids,
            failed_fixture_ids,
        ) = self._classification(study, outcomes)
        result_ids = tuple(item.replay_result_id for item in outcomes)
        identity = {
            "study_id": study.study_id,
            "failure_snapshot_id": study.failure_snapshot_id,
            "mechanism_id": study.mechanism_id,
            "policy": study.policy.to_payload(),
            "outcome_ids": [item.outcome_id for item in outcomes],
            "replay_result_ids": list(result_ids),
            "classification": classification.value,
            "unresolved_boundaries": list(boundaries),
        }
        profile = GeneralizationProfile(
            profile_id=f"generalization-{hashlib.sha256(_canonical(identity)).hexdigest()[:24]}",
            study_id=study.study_id,
            failure_snapshot_id=study.failure_snapshot_id,
            mechanism_id=study.mechanism_id,
            policy=study.policy,
            mutation_result_ids=result_ids,
            successful_mutation_fixture_ids=successful_fixture_ids,
            failed_mutation_fixture_ids=failed_fixture_ids,
            axis_successes=axis_successes,
            region_successes=region_successes,
            harder_successes=harder_successes,
            success_rate=success_rate,
            protected_failures=protected_failures,
            classification=classification,
            unresolved_boundaries=boundaries,
            metadata={
                "decision_id": study.decision_id,
                "outcome_count": len(outcomes),
                "successful_outcomes": len(successful_fixture_ids),
                "failed_outcomes": len(failed_fixture_ids),
                "policy_source": "MutationStudy.policy",
                "synthetic": study.synthetic,
            },
        )
        self.mutation_store.append_profile(profile)
        return profile

    def _current_state(self, failure_snapshot_id: str, mechanism_id: str) -> PromotionState:
        root = self.replay_store.get_failure(failure_snapshot_id)
        current = root.promotion_state
        for record in self.replay_store.records():
            if not isinstance(record, PromotionEvent):
                continue
            if record.failure_snapshot_id != failure_snapshot_id or record.mechanism_id != mechanism_id:
                continue
            if record.from_state is not current:
                raise ValueError("promotion event chain is not contiguous for mechanism")
            current = record.to_state
        return current

    def _promotion_event(
        self,
        profile: GeneralizationProfile,
        *,
        from_state: PromotionState,
        to_state: PromotionState,
    ) -> PromotionEvent:
        if from_state is not PromotionState.MOVEMENT or to_state is not PromotionState.TIER_CANDIDATE:
            raise ValueError("Stage 6 permits only MOVEMENT -> TIER_CANDIDATE")
        if profile.classification is not GeneralizationClass.PROMOTION_CANDIDATE:
            raise ValueError("only PROMOTION_CANDIDATE profiles may be promoted")
        if profile.protected_failures:
            raise ValueError("protected negative transfer is an absolute Stage-6 promotion veto")
        root = self.replay_store.get_failure(profile.failure_snapshot_id)
        if root.partition.value in {"FRESH", "SEALED"}:
            raise ValueError("Stage 6 cannot promote from FRESH or SEALED development evidence")
        evidence_ids = tuple(profile.mutation_result_ids)
        if not evidence_ids:
            raise ValueError("promotion requires mutation replay evidence")
        results = {
            record.replay_result_id: record
            for record in self.replay_store.records()
            if isinstance(record, ReplayResult)
        }
        if any(result_id not in results for result_id in evidence_ids):
            raise ValueError("promotion evidence replay result is missing")
        if any(results[result_id].failure_snapshot_id != profile.failure_snapshot_id for result_id in evidence_ids):
            raise ValueError("promotion evidence crosses root failure families")
        payload = {
            "failure_snapshot_id": profile.failure_snapshot_id,
            "mechanism_id": profile.mechanism_id,
            "generalization_profile_id": profile.profile_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "evidence_replay_result_ids": list(evidence_ids),
        }
        return PromotionEvent(
            promotion_event_id=f"promotion-stage6-{hashlib.sha256(_canonical(payload)).hexdigest()[:24]}",
            failure_snapshot_id=profile.failure_snapshot_id,
            mechanism_id=profile.mechanism_id,
            from_state=from_state,
            to_state=to_state,
            reason="registered Stage-6 neighborhood evidence satisfies promotion policy",
            evidence_replay_result_ids=evidence_ids,
            partition=root.partition,
            metadata={
                "stage": "STAGE_6",
                "generalization_profile_id": profile.profile_id,
                "classification": profile.classification.value,
                "certification_forbidden": True,
            },
        )

    def maybe_promote(self, profile: GeneralizationProfile) -> PromotionEvent | None:
        if not isinstance(profile, GeneralizationProfile):
            raise TypeError("profile must be GeneralizationProfile")
        validation = self.mutation_store.validate()
        if not validation.ok:
            raise ValueError("mutation evidence store integrity validation failed")
        stored = {item.profile_id: item for item in self.mutation_store.profiles(profile.study_id)}
        if stored.get(profile.profile_id) != profile:
            raise ValueError("profile is not the canonical stored generalization profile")
        if profile.protected_failures:
            return None
        if profile.classification is not GeneralizationClass.PROMOTION_CANDIDATE:
            return None
        current = self._current_state(profile.failure_snapshot_id, profile.mechanism_id)
        if current is PromotionState.TIER_CANDIDATE:
            return None
        if current is not PromotionState.MOVEMENT:
            return None
        event = self._promotion_event(
            profile,
            from_state=PromotionState.MOVEMENT,
            to_state=PromotionState.TIER_CANDIDATE,
        )
        self.replay_store.append(event)
        return event