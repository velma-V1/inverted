from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .test3_s0_types import (
    ActionRecord,
    CounterfactualRecord,
    CounterfactualStatus,
    FeatureProvenance,
    TransitionRecord,
)


@dataclass(frozen=True)
class ClassificationResult:
    status: CounterfactualStatus
    reason: str
    flags: tuple[str, ...] = ()
    dependency_audit: tuple[dict[str, Any], ...] = ()


def _feature_audit(features: Iterable[FeatureProvenance]) -> tuple[list[dict[str, Any]], list[str]]:
    audit: list[dict[str, Any]] = []
    invalid: list[str] = []
    for feature in features:
        row = asdict(feature)
        audit.append(row)
        lower_name = feature.feature_name.lower()
        dependencies = {str(item).lower() for item in feature.depends_on}
        if "hidden_gold" in lower_name or "gold_answer" in lower_name:
            invalid.append(f"hidden gold dependency in feature {feature.feature_name}")
        if any("hidden_gold" in dep or "gold_answer" in dep for dep in dependencies):
            invalid.append(f"hidden gold dependency in feature {feature.feature_name}")
        if feature.contains_post_action_dependency is True:
            invalid.append(f"post-action dependency in feature {feature.feature_name}")
        if feature.available_before_action is not True:
            invalid.append(f"temporal availability unresolved for feature {feature.feature_name}")
    return audit, invalid


def classify_counterfactual(
    changes_model_input: bool,
    needs_unobserved_model_output: bool,
    uses_hidden_gold_as_feature: bool,
    violates_temporal_availability: bool,
    provenance_complete: bool,
    action_possible: bool,
    *,
    feature_provenance: Iterable[FeatureProvenance] = (),
    downstream_after_new_model_output: bool = False,
    task_identity_complete: bool = True,
) -> ClassificationResult:
    dependency_audit, feature_invalid = _feature_audit(feature_provenance)
    invalid_flags: list[str] = []
    if uses_hidden_gold_as_feature:
        invalid_flags.append("hidden gold used as production feature")
    if violates_temporal_availability:
        invalid_flags.append("temporal availability violated")
    if not provenance_complete:
        invalid_flags.append("provenance incomplete")
    if not task_identity_complete:
        invalid_flags.append("task identity incomplete")
    if not action_possible:
        invalid_flags.append("action impossible in historical state")
    invalid_flags.extend(feature_invalid)
    if invalid_flags:
        return ClassificationResult(
            status=CounterfactualStatus.INVALID_COUNTERFACTUAL,
            reason="; ".join(invalid_flags),
            flags=tuple(invalid_flags),
            dependency_audit=tuple(dependency_audit),
        )

    inference_flags: list[str] = []
    if changes_model_input:
        inference_flags.append("proposed action changes model input/context")
    if needs_unobserved_model_output:
        inference_flags.append("requires unobserved model-role-task output")
    if downstream_after_new_model_output:
        inference_flags.append("observed downstream step follows a new model-producing mutation")
    if inference_flags:
        return ClassificationResult(
            status=CounterfactualStatus.REQUIRES_NEW_INFERENCE,
            reason="; ".join(inference_flags),
            flags=tuple(inference_flags),
            dependency_audit=tuple(dependency_audit),
        )

    return ClassificationResult(
        status=CounterfactualStatus.CAUSAL_REPLAY,
        reason="all required outputs are observed and recomposition does not change model inputs",
        dependency_audit=tuple(dependency_audit),
    )


def _status_for_transition(transition: TransitionRecord) -> ClassificationResult:
    features = transition.state_before.feature_provenance
    provenance_complete = bool(transition.provenance and transition.raw_record_hash and transition.state_before.task_id)
    action_possible = transition.action.component not in {"", "unknown", None}
    return classify_counterfactual(
        changes_model_input=transition.action.changes_model_input,
        needs_unobserved_model_output=False,
        uses_hidden_gold_as_feature=False,
        violates_temporal_availability=False,
        provenance_complete=provenance_complete,
        action_possible=action_possible,
        feature_provenance=features,
        downstream_after_new_model_output=False,
        task_identity_complete=bool(transition.state_before.task_id),
    )


def enumerate_replay_candidates(transitions: Iterable[TransitionRecord]) -> list[CounterfactualRecord]:
    rows = list(transitions)
    out: list[CounterfactualRecord] = []
    for transition in rows:
        classification = _status_for_transition(transition)
        out.append(CounterfactualRecord(
            counterfactual_id=f"single:{transition.transition_id}",
            source_transition_ids=(transition.transition_id,),
            proposed_actions=(transition.action,),
            status=classification.status,
            reason=classification.reason,
            dependency_audit=classification.dependency_audit,
            invalidity_flags=classification.flags if classification.status is CounterfactualStatus.INVALID_COUNTERFACTUAL else (),
            metadata={"kind": "observed_single_step_replay"},
        ))

    # Recompose already-observed actions for the same task only. This does not
    # claim the new order is causal if an earlier action changes model input;
    # those sequences are explicitly queued for new inference.
    by_task: dict[str, list[TransitionRecord]] = {}
    for transition in rows:
        by_task.setdefault(transition.state_before.task_id, []).append(transition)
    for task_id, task_rows in by_task.items():
        task_rows = sorted(task_rows, key=lambda row: (row.transition_index is None, row.transition_index or 0, row.transition_id))
        if len(task_rows) < 2:
            continue
        for left, right in zip(task_rows, task_rows[1:]):
            features = tuple(left.state_before.feature_provenance) + tuple(right.state_before.feature_provenance)
            classification = classify_counterfactual(
                changes_model_input=left.action.changes_model_input or right.action.changes_model_input,
                needs_unobserved_model_output=False,
                uses_hidden_gold_as_feature=False,
                violates_temporal_availability=False,
                provenance_complete=bool(left.provenance and right.provenance),
                action_possible=left.action.component != "unknown" and right.action.component != "unknown",
                feature_provenance=features,
                downstream_after_new_model_output=left.action.produces_new_model_output,
                task_identity_complete=bool(task_id),
            )
            out.append(CounterfactualRecord(
                counterfactual_id=f"pair:{left.transition_id}:{right.transition_id}",
                source_transition_ids=(left.transition_id, right.transition_id),
                proposed_actions=(left.action, right.action),
                status=classification.status,
                reason=classification.reason,
                dependency_audit=classification.dependency_audit,
                invalidity_flags=classification.flags if classification.status is CounterfactualStatus.INVALID_COUNTERFACTUAL else (),
                metadata={"kind": "adjacent_observed_recomposition", "task_id": task_id},
            ))
    return out


def audit_counterfactuals(records: Iterable[CounterfactualRecord]) -> dict[str, Any]:
    rows = list(records)
    counts = {status.value: 0 for status in CounterfactualStatus}
    reasons: dict[str, int] = {}
    for row in rows:
        counts[row.status.value] += 1
        reasons[row.reason] = reasons.get(row.reason, 0) + 1
    return {
        "total": len(rows),
        "counts": counts,
        "reasons": dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
        "causal_replay": [row for row in rows if row.status is CounterfactualStatus.CAUSAL_REPLAY],
        "requires_new_inference": [row for row in rows if row.status is CounterfactualStatus.REQUIRES_NEW_INFERENCE],
        "invalid": [row for row in rows if row.status is CounterfactualStatus.INVALID_COUNTERFACTUAL],
    }
