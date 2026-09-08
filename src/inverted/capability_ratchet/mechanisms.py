"""Causal mechanism localization over matched V3 replay outcomes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .causal_core import InterventionDefinition, InterventionKind, MechanismRole
from .causal_store import CausalEvidenceStore
from .core import (
    MechanismLabel,
    PromotionEvent,
    PromotionState,
    ReplayRequest,
    ReplayResult,
    to_payload,
)
from .replay_store import ReplayStore


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _stable_id(prefix: str, payload: object) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(payload)).hexdigest()[:24]}"


def _success(result: ReplayResult) -> bool:
    return (
        result.completed
        and result.semantic_pass
        and result.contract_pass
        and not result.failure_classes
    )


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


@dataclass(frozen=True)
class MechanismAssessment:
    labels: tuple[MechanismLabel, ...]
    supported_hypotheses: tuple[str, ...]
    falsified_hypotheses: tuple[str, ...]
    promotion_events: tuple[PromotionEvent, ...]
    next_decisions: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "labels", tuple(self.labels))
        object.__setattr__(self, "supported_hypotheses", tuple(self.supported_hypotheses))
        object.__setattr__(self, "falsified_hypotheses", tuple(self.falsified_hypotheses))
        object.__setattr__(self, "promotion_events", tuple(self.promotion_events))
        object.__setattr__(self, "next_decisions", tuple(self.next_decisions))


@dataclass(frozen=True)
class _ObservedBranch:
    request: ReplayRequest
    result: ReplayResult
    intervention: InterventionDefinition


class MechanismLocalizer:
    """Classify matched causal replay evidence without mutating source fixtures."""

    def __init__(self, replay_store: ReplayStore, causal_store: CausalEvidenceStore) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store

    @staticmethod
    def _same_result(a: ReplayResult, b: ReplayResult) -> bool:
        left = to_payload(a)
        right = to_payload(b)
        left.pop("record_id", None)
        right.pop("record_id", None)
        return left == right

    def _observe(
        self,
        failure_snapshot_id: str,
        replay_results: Iterable[ReplayResult],
    ) -> tuple[object, tuple[_ObservedBranch, ...]]:
        replay_validation = self.replay_store.validate()
        if not replay_validation.ok:
            raise ValueError("replay store integrity validation failed")
        causal_validation = self.causal_store.validate()
        if not causal_validation.ok:
            raise ValueError("causal evidence store integrity validation failed")
        root = self.replay_store.get_failure(failure_snapshot_id)
        if root.parent_failure_snapshot_id is not None:
            raise ValueError("mechanism localization requires an originating root failure")

        records = self.replay_store.records()
        requests = {
            record.replay_request_id: record
            for record in records
            if isinstance(record, ReplayRequest)
        }
        committed_results = {
            record.replay_result_id: record
            for record in records
            if isinstance(record, ReplayResult)
        }
        observed: list[_ObservedBranch] = []
        for supplied in replay_results:
            if not isinstance(supplied, ReplayResult):
                raise TypeError("replay_results must contain ReplayResult values")
            committed = committed_results.get(supplied.replay_result_id)
            if committed is None or not self._same_result(committed, supplied):
                raise ValueError("replay result is not committed canonical evidence")
            if supplied.failure_snapshot_id != root.failure_snapshot_id:
                raise ValueError("replay result belongs to a different failure family")
            if supplied.parent_failure_snapshot_id != root.failure_snapshot_id:
                raise ValueError("replay result parent lineage differs from the compared state")
            if supplied.parent_state_hash != root.state_hash:
                raise ValueError("replay result parent state differs from the compared state")
            request = requests.get(supplied.replay_request_id)
            if request is None:
                raise ValueError("replay result is missing its replay request")
            if (
                request.parent_failure_snapshot_id != root.failure_snapshot_id
                or request.parent_state_hash != root.state_hash
            ):
                raise ValueError("replay request parent state differs from the compared state")
            intervention = self.causal_store.get_intervention(request.intervention_id)
            if intervention.failure_snapshot_id != root.failure_snapshot_id:
                raise ValueError("intervention belongs to a different failure lineage")
            if intervention.parent_state_hash != root.state_hash:
                raise ValueError("intervention parent state differs from the compared state")
            if intervention.hypothesis_id != request.hypothesis_id:
                raise ValueError("replay request hypothesis/intervention mismatch")
            observed.append(_ObservedBranch(request, committed, intervention))
        if not observed:
            raise ValueError("mechanism localization requires replay results")
        return root, tuple(observed)

    @staticmethod
    def _mechanism_id(
        failure_snapshot_id: str,
        hypothesis_id: str,
        intervention_ids: tuple[str, ...],
        role: MechanismRole,
    ) -> str:
        return _stable_id("mechanism", {
            "failure_snapshot_id": failure_snapshot_id,
            "hypothesis_id": hypothesis_id,
            "intervention_ids": intervention_ids,
            "role": role.value,
        })

    def _label(
        self,
        root,
        *,
        hypothesis_id: str,
        intervention_ids: tuple[str, ...],
        role: MechanismRole,
        evidence: tuple[ReplayResult, ...],
        confidence: float,
        metadata: dict[str, object] | None = None,
    ) -> MechanismLabel:
        ids = _unique(intervention_ids)
        result_ids = _unique(result.replay_result_id for result in evidence)
        mechanism_id = self._mechanism_id(
            root.failure_snapshot_id, hypothesis_id, ids, role
        )
        label_id = _stable_id("mechanism-label", {
            "mechanism_id": mechanism_id,
            "evidence": result_ids,
            "parent_state_hash": root.state_hash,
        })
        label = MechanismLabel(
            mechanism_label_id=label_id,
            failure_snapshot_id=root.failure_snapshot_id,
            parent_failure_snapshot_id=root.failure_snapshot_id,
            parent_state_hash=root.state_hash,
            mechanism_id=mechanism_id,
            hypothesis_id=hypothesis_id,
            intervention_ids=ids,
            role=role,
            evidence_replay_result_ids=result_ids,
            confidence=confidence,
            metadata={} if metadata is None else metadata,
        )
        self.replay_store.append(label)
        return label

    def _promotion(
        self,
        root,
        label: MechanismLabel,
        evidence: tuple[ReplayResult, ...],
    ) -> PromotionEvent | None:
        existing = [
            record
            for record in self.replay_store.records()
            if isinstance(record, PromotionEvent)
            and record.failure_snapshot_id == root.failure_snapshot_id
            and record.mechanism_id == label.mechanism_id
        ]
        if existing:
            if existing[-1].to_state is PromotionState.MOVEMENT:
                return existing[-1]
            return None
        result_ids = _unique(result.replay_result_id for result in evidence)
        event_id = _stable_id("promotion", {
            "failure_snapshot_id": root.failure_snapshot_id,
            "mechanism_id": label.mechanism_id,
            "to_state": PromotionState.MOVEMENT.value,
            "evidence": result_ids,
        })
        event = PromotionEvent(
            promotion_event_id=event_id,
            failure_snapshot_id=root.failure_snapshot_id,
            mechanism_id=label.mechanism_id,
            from_state=PromotionState.UNASSESSED,
            to_state=PromotionState.MOVEMENT,
            reason="targeted treatment beat its matched sham on the same parent state",
            evidence_replay_result_ids=result_ids,
            partition=root.partition,
            metadata={"single_instance": True, "certification_forbidden": True},
        )
        self.replay_store.append(event)
        return event

    @staticmethod
    def _by_hypothesis(observed: tuple[_ObservedBranch, ...]) -> dict[str, list[_ObservedBranch]]:
        grouped: dict[str, list[_ObservedBranch]] = {}
        for branch in observed:
            grouped.setdefault(branch.request.hypothesis_id, []).append(branch)
        return grouped

    @staticmethod
    def _result_for_intervention(
        branches: list[_ObservedBranch], intervention_id: str
    ) -> ReplayResult | None:
        matches = [
            branch.result for branch in branches
            if branch.intervention.intervention_id == intervention_id
        ]
        if len(matches) > 1:
            raise ValueError("duplicate replay outcomes for one intervention are ambiguous")
        return matches[0] if matches else None

    def evaluate(
        self,
        failure_snapshot_id: str,
        replay_results: Iterable[ReplayResult],
    ) -> MechanismAssessment:
        root, observed = self._observe(failure_snapshot_id, replay_results)
        labels: list[MechanismLabel] = []
        supported: list[str] = []
        falsified: list[str] = []
        promotions: list[PromotionEvent] = []
        next_decisions: list[str] = []

        for hypothesis_id, branches in self._by_hypothesis(observed).items():
            hypotheses = {
                item.hypothesis_id: item
                for item in self.causal_store.hypotheses(root.failure_snapshot_id)
            }
            if hypothesis_id not in hypotheses:
                raise ValueError("replay outcome references an unregistered hypothesis")

            targets = [
                branch for branch in branches
                if branch.intervention.kind not in {InterventionKind.SHAM, InterventionKind.ABLATION}
            ]
            shams = [branch for branch in branches if branch.intervention.kind is InterventionKind.SHAM]
            ablations = [branch for branch in branches if branch.intervention.kind is InterventionKind.ABLATION]

            # Every target/sham causal pair must share the exact counterfactual group.
            for target in targets:
                matched = [
                    sham for sham in shams
                    if sham.intervention.sham_for == target.intervention.intervention_id
                ]
                for sham in matched:
                    if sham.request.counterfactual_group_id != target.request.counterfactual_group_id:
                        raise ValueError("target and sham counterfactual groups differ")

            successful_targets = [branch for branch in targets if _success(branch.result)]
            failed_targets = [branch for branch in targets if not _success(branch.result)]
            causal_targets: list[tuple[_ObservedBranch, tuple[_ObservedBranch, ...]]] = []
            nonspecific_targets: list[tuple[_ObservedBranch, tuple[_ObservedBranch, ...]]] = []
            harmful_targets: list[tuple[_ObservedBranch, tuple[_ObservedBranch, ...]]] = []

            for target in targets:
                matched = tuple(
                    sham for sham in shams
                    if sham.intervention.sham_for == target.intervention.intervention_id
                )
                if not matched:
                    continue
                if _success(target.result) and all(not _success(sham.result) for sham in matched):
                    causal_targets.append((target, matched))
                elif _success(target.result) and any(_success(sham.result) for sham in matched):
                    nonspecific_targets.append((target, matched))
                elif not _success(target.result) and any(_success(sham.result) for sham in matched):
                    harmful_targets.append((target, matched))

            if causal_targets:
                supported.append(hypothesis_id)
            elif harmful_targets or (targets and not successful_targets):
                falsified.append(hypothesis_id)

            for target, matched in causal_targets:
                intervention = target.intervention
                pair_evidence = (target.result,) + tuple(sham.result for sham in matched)
                role_labels: list[MechanismLabel] = []

                if intervention.composition:
                    composition = intervention.composition
                    ablation_map: dict[str, ReplayResult] = {}
                    for ablation in ablations:
                        for component in ablation.intervention.ablates:
                            ablation_map[component] = ablation.result

                    if ablation_map:
                        for component in _unique(composition):
                            ablation_result = ablation_map.get(component)
                            if ablation_result is None:
                                continue
                            role = (
                                MechanismRole.REDUNDANT
                                if _success(ablation_result)
                                else MechanismRole.REQUIRED
                            )
                            role_labels.append(self._label(
                                root,
                                hypothesis_id=hypothesis_id,
                                intervention_ids=(component,),
                                role=role,
                                evidence=pair_evidence + (ablation_result,),
                                confidence=0.9 if role is MechanismRole.REQUIRED else 0.8,
                                metadata={"compound_intervention_id": intervention.intervention_id},
                            ))
                    else:
                        component_results = {
                            item.intervention.intervention_id: item.result
                            for item in targets
                            if not item.intervention.composition
                        }
                        unique_components = _unique(composition)
                        singles_fail = all(
                            component in component_results
                            and not _success(component_results[component])
                            for component in unique_components
                        )
                        if singles_fail and len(unique_components) >= 2:
                            if intervention.kind is InterventionKind.DELIVERY:
                                role_labels.append(self._label(
                                    root,
                                    hypothesis_id=hypothesis_id,
                                    intervention_ids=(unique_components[0],),
                                    role=MechanismRole.ENABLER,
                                    evidence=pair_evidence + tuple(component_results[c] for c in unique_components),
                                    confidence=0.8,
                                    metadata={"ordered_compound": intervention.intervention_id},
                                ))
                            else:
                                role_labels.append(self._label(
                                    root,
                                    hypothesis_id=hypothesis_id,
                                    intervention_ids=unique_components,
                                    role=MechanismRole.SYNERGIST,
                                    evidence=pair_evidence + tuple(component_results[c] for c in unique_components),
                                    confidence=0.85,
                                    metadata={"compound_intervention_id": intervention.intervention_id},
                                ))
                        if len(composition) != len(unique_components):
                            repeated = tuple(
                                item for item in unique_components if composition.count(item) > 1
                            )
                            if repeated:
                                role_labels.append(self._label(
                                    root,
                                    hypothesis_id=hypothesis_id,
                                    intervention_ids=repeated,
                                    role=MechanismRole.REANCHOR,
                                    evidence=pair_evidence,
                                    confidence=0.75,
                                    metadata={"sequence": list(composition)},
                                ))
                else:
                    role_labels.append(self._label(
                        root,
                        hypothesis_id=hypothesis_id,
                        intervention_ids=(intervention.intervention_id,),
                        role=MechanismRole.REQUIRED,
                        evidence=pair_evidence,
                        confidence=0.9,
                    ))

                if not role_labels:
                    role_labels.append(self._label(
                        root,
                        hypothesis_id=hypothesis_id,
                        intervention_ids=(intervention.intervention_id,),
                        role=MechanismRole.CONDITIONAL,
                        evidence=pair_evidence,
                        confidence=0.7,
                    ))
                labels.extend(role_labels)
                event = self._promotion(root, role_labels[0], pair_evidence)
                if event is not None:
                    promotions.append(event)

            for target, matched in nonspecific_targets:
                evidence = (target.result,) + tuple(sham.result for sham in matched)
                labels.append(self._label(
                    root,
                    hypothesis_id=hypothesis_id,
                    intervention_ids=(target.intervention.intervention_id,),
                    role=MechanismRole.UNRESOLVED,
                    evidence=evidence,
                    confidence=0.4,
                    metadata={"reason": "target and matched sham both passed"},
                ))
                next_decisions.append(
                    f"design a stronger falsification control for hypothesis {hypothesis_id}"
                )

            for target, matched in harmful_targets:
                evidence = (target.result,) + tuple(sham.result for sham in matched)
                labels.append(self._label(
                    root,
                    hypothesis_id=hypothesis_id,
                    intervention_ids=(target.intervention.intervention_id,),
                    role=MechanismRole.HARMFUL,
                    evidence=evidence,
                    confidence=0.9,
                    metadata={"reason": "target failed while matched sham passed"},
                ))
                next_decisions.append(
                    f"exclude or condition harmful intervention {target.intervention.intervention_id}"
                )

            # Suppression is visible even when the compound itself does not earn movement:
            # a successful prefix becomes unsuccessful after an added component.
            for target in failed_targets:
                composition = target.intervention.composition
                if len(composition) < 2:
                    continue
                prefix_id = composition[0]
                prefix_result = self._result_for_intervention(branches, prefix_id)
                if prefix_result is not None and _success(prefix_result):
                    for component in _unique(composition[1:]):
                        labels.append(self._label(
                            root,
                            hypothesis_id=hypothesis_id,
                            intervention_ids=(component,),
                            role=MechanismRole.SUPPRESSOR,
                            evidence=(prefix_result, target.result),
                            confidence=0.85,
                            metadata={"failed_compound": target.intervention.intervention_id},
                        ))

            if not causal_targets and not nonspecific_targets and not harmful_targets and not labels:
                evidence = tuple(branch.result for branch in branches)
                if evidence:
                    labels.append(self._label(
                        root,
                        hypothesis_id=hypothesis_id,
                        intervention_ids=_unique(
                            branch.intervention.intervention_id for branch in branches
                        ),
                        role=MechanismRole.UNRESOLVED,
                        evidence=evidence,
                        confidence=0.25,
                        metadata={"reason": "insufficient matched causal geometry"},
                    ))
                next_decisions.append(
                    f"collect a matched target/sham result for hypothesis {hypothesis_id}"
                )

        promotion_by_id = {
            event.promotion_event_id: event
            for event in promotions
        }
        return MechanismAssessment(
            labels=tuple(labels),
            supported_hypotheses=_unique(supported),
            falsified_hypotheses=_unique(falsified),
            promotion_events=tuple(promotion_by_id.values()),
            next_decisions=_unique(next_decisions),
        )

    def _causal_manifest_hash(self) -> str:
        pieces: list[bytes] = []
        for path in (
            self.causal_store.hypothesis_manifest_path,
            self.causal_store.intervention_manifest_path,
        ):
            pieces.append(path.read_bytes() if path.exists() else b"")
        return hashlib.sha256(b"".join(pieces)).hexdigest()

    @property
    def mechanism_graph_path(self) -> Path:
        return self.causal_store.root / "mechanism-graph.json"

    def rebuild_graph(self) -> Path:
        replay_validation = self.replay_store.validate()
        if not replay_validation.ok:
            raise ValueError("replay store integrity validation failed")
        causal_validation = self.causal_store.validate()
        if not causal_validation.ok:
            raise ValueError("causal evidence store integrity validation failed")
        records = self.replay_store.records()
        labels = [record for record in records if isinstance(record, MechanismLabel)]
        promotions = [record for record in records if isinstance(record, PromotionEvent)]
        payload = {
            "header": {
                "test_replay_sha256": self.replay_store.manifest_path.read_text(
                    encoding="ascii"
                ).strip(),
                "causal_store_manifest_sha256": self._causal_manifest_hash(),
            },
            "mechanisms": [
                {
                    "mechanism_label_id": label.mechanism_label_id,
                    "mechanism_id": label.mechanism_id,
                    "failure_snapshot_id": label.failure_snapshot_id,
                    "hypothesis_id": label.hypothesis_id,
                    "intervention_ids": list(label.intervention_ids),
                    "role": label.role.value,
                    "evidence_replay_result_ids": list(label.evidence_replay_result_ids),
                    "confidence": label.confidence,
                }
                for label in sorted(labels, key=lambda item: item.mechanism_label_id)
            ],
            "promotions": [
                {
                    "promotion_event_id": event.promotion_event_id,
                    "failure_snapshot_id": event.failure_snapshot_id,
                    "mechanism_id": event.mechanism_id,
                    "from_state": event.from_state.value,
                    "to_state": event.to_state.value,
                    "evidence_replay_result_ids": list(event.evidence_replay_result_ids),
                }
                for event in sorted(promotions, key=lambda item: item.promotion_event_id)
            ],
        }
        encoded = _canonical(payload) + b"\n"
        self.mechanism_graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.mechanism_graph_path.write_bytes(encoded)
        return self.mechanism_graph_path
