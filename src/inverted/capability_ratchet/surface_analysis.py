"""Evidence-derived operating-band analysis for V3 Stage 5."""

from __future__ import annotations

from collections import defaultdict
from numbers import Real
from typing import Any

from inverted.universal_tuning.statistics import (
    NONINFERIORITY_MARGIN,
    SUPERIORITY_MARGIN,
    PairedBatch,
    classify_comparison,
    paired_bootstrap_ci,
)

from .surface_core import (
    OperatingSurfaceProfile,
    SurfaceBand,
    SurfaceCallGeometry,
    SurfaceDisposition,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfaceStudy,
)


def _capability_pass(row: SurfaceObservation) -> bool:
    metrics = row.metrics
    return bool(
        metrics.get("completed")
        and metrics.get("semantic_pass")
        and metrics.get("contract_pass")
        and not metrics.get("reasoning_cap_exhausted", False)
    )


def _physical_calls(row: SurfaceObservation) -> int:
    value = row.metrics.get("physical_calls", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _negative_transfer(row: SurfaceObservation) -> bool:
    metrics = row.metrics
    return bool(
        metrics.get("protected_control_baseline_pass") is True
        and metrics.get("protected_control_candidate_pass") is False
    )


class SurfaceAnalyzer:
    """Infer one causal operating band from stored same-parent observations."""

    def __init__(self, surface_store) -> None:
        self.surface_store = surface_store

    def _study(self, study_id: str) -> SurfaceStudy:
        matches = [item for item in self.surface_store.studies() if item.study_id == study_id]
        if len(matches) != 1:
            raise ValueError("surface study must resolve to exactly one stored study")
        study = matches[0]
        if len(study.axes) != 1:
            raise ValueError("Stage-5 analysis requires one causal axis at a time")
        return study

    def _causal_rows(self, study: SurfaceStudy) -> tuple[SurfaceObservation, ...]:
        rows = tuple(
            row for row in self.surface_store.observations(study.study_id)
            if row.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL
        )
        if not rows:
            raise ValueError("operating-surface bounds require same-state causal evidence")
        return rows

    @staticmethod
    def _supported_pass(rows: tuple[SurfaceObservation, ...]) -> bool:
        if not rows:
            return False
        rate = sum(1.0 if _capability_pass(row) else 0.0 for row in rows) / len(rows)
        grouped: dict[str, list[SurfaceObservation]] = defaultdict(list)
        paired_complete = True
        for row in rows:
            batch_id = row.metrics.get("paired_batch_id")
            baseline = row.metrics.get("paired_baseline_pass")
            if not isinstance(batch_id, str) or not batch_id or type(baseline) is not bool:
                paired_complete = False
                break
            grouped[batch_id].append(row)
        if paired_complete and grouped:
            batches = tuple(
                PairedBatch(
                    batch_id=batch_id,
                    baseline=tuple(1.0 if item.metrics["paired_baseline_pass"] else 0.0 for item in members),
                    candidate=tuple(1.0 if _capability_pass(item) else 0.0 for item in members),
                )
                for batch_id, members in sorted(grouped.items())
            )
            comparison = paired_bootstrap_ci(batches)
            if classify_comparison(comparison) == "INFERIOR":
                return False
        return rate >= 0.5 + SUPERIORITY_MARGIN

    def _summarize(self, study: SurfaceStudy, rows: tuple[SurfaceObservation, ...]):
        axis = study.axes[0]
        registered = tuple(study.axis_values[axis.value])
        grouped: dict[Any, list[SurfaceObservation]] = defaultdict(list)
        for row in rows:
            if row.axis is not axis:
                raise ValueError("surface observation axis differs from its study")
            grouped[row.value].append(row)
        observed = tuple(value for value in registered if value in grouped)
        passing = tuple(
            value for value in observed
            if self._supported_pass(tuple(grouped[value]))
        )
        return axis, registered, grouped, observed, passing

    @staticmethod
    def _geometry(rows: tuple[SurfaceObservation, ...]) -> SurfaceCallGeometry:
        total = sum(_physical_calls(row) for row in rows)
        protected = sum(_physical_calls(row) for row in rows if row.protected_exploration)
        return SurfaceCallGeometry(
            minimum_physical_calls=total,
            expected_physical_calls=total,
            worst_case_physical_calls=total,
            protected_exploration_calls=protected,
        )

    @staticmethod
    def _negative_transfer_present(rows: tuple[SurfaceObservation, ...]) -> bool:
        return any(_negative_transfer(row) for row in rows)

    @staticmethod
    def _first_harm_after_useful(registered, grouped, passing):
        if not passing:
            return None
        first_index = registered.index(passing[0])
        for value in registered[first_index + 1:]:
            if value in grouped and value not in passing:
                return value
        return None

    def analyze(self, study_id: str) -> OperatingSurfaceProfile:
        study = self._study(study_id)
        rows = self._causal_rows(study)
        axis, registered, grouped, observed, passing = self._summarize(study, rows)
        unresolved = tuple(value for value in registered if value not in grouped)
        harm_onset = self._first_harm_after_useful(registered, grouped, passing)

        if not passing:
            disposition = SurfaceDisposition.NO_USEFUL_REGION
            lower_useful = upper_useful = None
            recommended = ()
        else:
            lower_useful = passing[0]
            pre_harm = tuple(
                value for value in passing
                if harm_onset is None or registered.index(value) < registered.index(harm_onset)
            )
            upper_useful = pre_harm[-1] if pre_harm else passing[-1]
            recommended = pre_harm if pre_harm else passing
            if self._negative_transfer_present(rows):
                disposition = SurfaceDisposition.NEGATIVE_TRANSFER
                recommended = passing
                upper_useful = passing[-1]
            elif harm_onset is not None:
                disposition = SurfaceDisposition.HARM_BOUNDARY
            elif len(observed) == len(registered) and len(passing) == len(observed):
                disposition = SurfaceDisposition.PLATEAU
            else:
                disposition = SurfaceDisposition.USEFUL_BAND

        evidence_ids = tuple(row.observation_id for row in rows)
        band = SurfaceBand(
            axis=axis,
            disposition=disposition,
            lower_useful=lower_useful,
            upper_useful=upper_useful,
            recommended_region=recommended,
            harm_onset=harm_onset,
            evidence_observation_ids=evidence_ids,
            unresolved_edges=unresolved,
        )
        profile = OperatingSurfaceProfile.create(
            study=study,
            band=band,
            evidence_refs=evidence_ids,
            call_geometry=self._geometry(rows),
        )
        self.surface_store.append_profile(profile)
        return profile
