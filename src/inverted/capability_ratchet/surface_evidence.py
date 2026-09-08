"""Zero-call evidence reuse for V3 Stage-5 operating-surface studies."""

from __future__ import annotations

from typing import Any

from .causal_store import CausalEvidenceStore
from .core import MechanismLabel, ReplayMode, ReplayRequest, ReplayResult
from .historical import V2EvidenceSource
from .replay_store import ReplayStore
from .surface_core import (
    SurfaceAxis,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfacePoint,
    SurfaceStudy,
)
from .surface_store import SurfaceEvidenceStore


class SurfaceEvidenceCompiler:
    """Reuse canonical same-state evidence and import V2 observations as priors."""

    def __init__(
        self,
        replay_store: ReplayStore,
        causal_store: CausalEvidenceStore,
        surface_store: SurfaceEvidenceStore,
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

    def _hypothesis_ids(self, study: SurfaceStudy) -> frozenset[str]:
        return frozenset(
            record.hypothesis_id
            for record in self.replay_store.records()
            if isinstance(record, MechanismLabel)
            and record.failure_snapshot_id == study.failure_snapshot_id
            and record.mechanism_id == study.mechanism_id
            and record.parent_state_hash == study.parent_state_hash
        )

    @staticmethod
    def _baseline_value(study: SurfaceStudy, axis: SurfaceAxis, profile: Any) -> Any | None:
        if not isinstance(profile, dict) and not hasattr(profile, "get"):
            return None
        if axis is SurfaceAxis.REASONING_BUDGET:
            return profile.get("thinking_budget")
        if axis is SurfaceAxis.TEMPERATURE:
            return profile.get("temperature")
        return None

    @staticmethod
    def _override_value(request: ReplayRequest, axis: SurfaceAxis) -> Any | None:
        if request.mode is ReplayMode.EXACT:
            return None
        matches: list[Any] = []
        for dimension in request.changed_dimensions:
            if dimension not in request.overrides:
                continue
            lowered = dimension.lower()
            if axis is SurfaceAxis.REASONING_BUDGET and (
                lowered.endswith("thinking_budget") or lowered.endswith("options.num_predict")
            ):
                matches.append(request.overrides[dimension])
            elif axis is SurfaceAxis.TEMPERATURE and (
                lowered.endswith("temperature") or lowered.endswith("options.temperature")
            ):
                matches.append(request.overrides[dimension])
        if not matches:
            return None
        unique = []
        for value in matches:
            if value not in unique:
                unique.append(value)
        if len(unique) != 1:
            raise ValueError(f"replay request ambiguously changes {axis.value}")
        return unique[0]

    def _point_for_request(
        self,
        study: SurfaceStudy,
        request: ReplayRequest,
        axis: SurfaceAxis,
    ) -> SurfacePoint | None:
        fixture = self.replay_store.get_failure(study.failure_snapshot_id)
        value = (
            self._baseline_value(study, axis, fixture.inference_profile)
            if request.mode is ReplayMode.EXACT
            else self._override_value(request, axis)
        )
        if value is None or value not in study.axis_values[axis.value]:
            return None
        protected = False
        if request.intervention_id:
            try:
                protected = self.causal_store.get_intervention(request.intervention_id).protected_exploration
            except (KeyError, ValueError):
                protected = False
        return SurfacePoint.create(
            study=study,
            axis=axis,
            value=value,
            decision_id=request.decision_id,
            protected_exploration=protected,
        )

    @staticmethod
    def _result_metrics(result: ReplayResult) -> dict[str, Any]:
        metrics = dict(result.metrics)
        metrics.update({
            "completed": result.completed,
            "semantic_pass": result.semantic_pass,
            "contract_pass": result.contract_pass,
            "failure_classes": list(result.failure_classes),
            "physical_calls": int(result.metrics.get("physical_calls", 0) or 0),
            "MODEL_CALLS": 0,
        })
        return metrics

    def same_state_observations(self, study: SurfaceStudy) -> tuple[SurfaceObservation, ...]:
        """Materialize reusable same-parent replay outcomes as zero-call observations."""
        if not isinstance(study, SurfaceStudy):
            raise TypeError("study must be SurfaceStudy")
        hypothesis_ids = self._hypothesis_ids(study)
        if not hypothesis_ids:
            raise ValueError("surface study has no canonical mechanism hypotheses")
        records = self.replay_store.records()
        requests = {
            record.replay_request_id: record
            for record in records
            if isinstance(record, ReplayRequest)
        }
        rows: list[SurfaceObservation] = []
        for result in records:
            if not isinstance(result, ReplayResult):
                continue
            if (
                result.failure_snapshot_id != study.failure_snapshot_id
                or result.parent_failure_snapshot_id != study.failure_snapshot_id
                or result.parent_state_hash != study.parent_state_hash
                or result.partition != study.partition
                or result.mode is ReplayMode.CROSS_MODEL
            ):
                continue
            request = requests.get(result.replay_request_id)
            if request is None or request.hypothesis_id not in hypothesis_ids:
                continue
            if (
                request.parent_failure_snapshot_id != study.failure_snapshot_id
                or request.parent_state_hash != study.parent_state_hash
                or request.partition != study.partition
            ):
                continue
            for axis in study.axes:
                point = self._point_for_request(study, request, axis)
                if point is None:
                    continue
                observation = SurfaceObservation.create(
                    point=point,
                    evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
                    replay_result_ids=(result.replay_result_id,),
                    metrics=self._result_metrics(result),
                )
                self.surface_store.append_observation(observation)
                rows.append(observation)
        return tuple(sorted(rows, key=lambda item: (item.axis.value, repr(item.value), item.observation_id)))

    @staticmethod
    def _trial_id(observation: Any, row: dict[str, Any]) -> str | None:
        top = row.get("trial_id")
        metadata = dict(observation.metadata).get("trial_id")
        if top is not None and metadata is not None and top != metadata:
            raise ValueError("V2 observation trial_id disagrees with metadata")
        trial = top if top is not None else metadata
        return trial if isinstance(trial, str) and trial else None

    @staticmethod
    def _reasoning_cap_exhausted(raw_trial: dict[str, Any] | None) -> bool:
        if not isinstance(raw_trial, dict):
            return False
        calls = raw_trial.get("raw_calls")
        if not isinstance(calls, list) or not calls:
            return False
        first = calls[0]
        if not isinstance(first, dict):
            return False
        request = first.get("request")
        response = first.get("response")
        return (
            isinstance(request, dict)
            and request.get("think") is True
            and isinstance(response, dict)
            and response.get("done_reason") == "length"
        )

    @staticmethod
    def _prior_value(axis: SurfaceAxis, observation: Any) -> Any | None:
        if axis is SurfaceAxis.REASONING_BUDGET:
            return observation.profile.thinking_budget
        if axis is SurfaceAxis.TEMPERATURE:
            return observation.profile.temperature
        return None

    def compile_v2_priors(
        self,
        source: V2EvidenceSource,
        study: SurfaceStudy,
    ) -> tuple[SurfaceObservation, ...]:
        """Import comparable V2 budget/temperature rows as non-causal ordering priors."""
        if not isinstance(source, V2EvidenceSource):
            raise TypeError("source must be V2EvidenceSource")
        if not isinstance(study, SurfaceStudy):
            raise TypeError("study must be SurfaceStudy")
        fixture = self.replay_store.get_failure(study.failure_snapshot_id)
        loaded = source.load()
        rows: list[SurfaceObservation] = []
        for observation, raw_row in zip(loaded.observations, loaded.observation_rows, strict=True):
            if observation.family != fixture.family:
                continue
            trial_id = self._trial_id(observation, raw_row)
            raw_trial = loaded.raw_trials.get(trial_id) if trial_id is not None else None
            cap_exhausted = self._reasoning_cap_exhausted(raw_trial)
            for axis in study.axes:
                value = self._prior_value(axis, observation)
                if value is None or value not in study.axis_values[axis.value]:
                    continue
                point = SurfacePoint.create(
                    study=study,
                    axis=axis,
                    value=value,
                    decision_id=study.decision_id,
                )
                failure_classes = [
                    item.value if hasattr(item, "value") else str(item)
                    for item in observation.failure_classes
                ]
                metrics = {
                    "completed": observation.completed,
                    "semantic_pass": observation.semantic_pass,
                    "contract_pass": observation.contract_pass,
                    "semantic_quality": observation.semantic_quality,
                    "contract_quality": observation.contract_quality,
                    "latency_s": observation.latency_s,
                    "output_tokens": observation.output_tokens,
                    "thinking_tokens": observation.thinking_tokens,
                    "physical_calls": observation.physical_calls,
                    "failure_classes": failure_classes,
                    "reasoning_cap_exhausted": cap_exhausted,
                    "MODEL_CALLS": 0,
                }
                refs = [
                    f"{loaded.campaign_id}:atomic_observations.jsonl:{observation.observation_id}"
                ]
                if trial_id is not None:
                    refs.append(f"{loaded.campaign_id}:raw_calls.jsonl:{trial_id}")
                prior = SurfaceObservation.create(
                    point=point,
                    evidence_kind=SurfaceEvidenceKind.HISTORICAL_PRIOR,
                    source_evidence_refs=tuple(refs),
                    metrics=metrics,
                )
                self.surface_store.append_observation(prior)
                rows.append(prior)
        return tuple(sorted(rows, key=lambda item: (item.axis.value, repr(item.value), item.observation_id)))

    def answered_points(self, study: SurfaceStudy) -> frozenset[str]:
        """Return all same-state points already answered, discovering canonical replays first."""
        self.same_state_observations(study)
        return frozenset(
            observation.surface_point_id
            for observation in self.surface_store.observations(study.study_id)
            if observation.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL
        )
