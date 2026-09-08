"""Deterministic hypothesis-to-intervention generation for V3 failure research."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .autopsy import AutopsyReport
from .causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    InterventionDefinition,
    InterventionKind,
)
from .causal_store import CausalEvidenceStore
from .core import FailureFixture, to_payload
from .replay_store import ReplayStore


class TailoredInterventionGenerator:
    """Compile autopsy hypotheses into small, falsifiable same-state treatments.

    Generation is deterministic and reads only the canonical model-visible replay
    payload plus the already-frozen autopsy report. Hidden oracle material is never
    consulted while constructing model-visible overrides.
    """

    def __init__(self, replay_store: ReplayStore, causal_store: CausalEvidenceStore) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store

    @staticmethod
    def _scientific_fixture_payload(fixture: FailureFixture) -> dict[str, Any]:
        payload = to_payload(fixture)
        payload.pop("record_id", None)
        return payload

    def _canonical_fixture(self, fixture: FailureFixture) -> FailureFixture:
        validation = self.replay_store.validate()
        if not validation.ok:
            raise ValueError("replay store integrity validation failed")
        current = self.replay_store.get_failure(fixture.failure_snapshot_id)
        if self._scientific_fixture_payload(current) != self._scientific_fixture_payload(fixture):
            raise ValueError("intervention fixture is not the active canonical replay failure")
        return current

    def _visible_payload(self, fixture: FailureFixture) -> Mapping[str, Any]:
        payload = self.replay_store.read_asset(fixture.model_visible_asset_sha256)
        if not isinstance(payload, Mapping):
            raise ValueError("model-visible replay asset must be a mapping")
        envelopes = payload.get("request_envelopes")
        if not isinstance(envelopes, list) or not envelopes or not isinstance(envelopes[0], Mapping):
            raise ValueError("model-visible replay asset requires request_envelopes")
        return payload

    @staticmethod
    def _message_dimension(visible: Mapping[str, Any]) -> tuple[str, str]:
        envelope = visible["request_envelopes"][0]
        messages = envelope.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("prompt/context intervention requires a visible message")
        index = len(messages) - 1
        message = messages[index]
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise ValueError("prompt/context intervention requires text message content")
        return f"request_envelopes.0.messages.{index}.content", message["content"]

    @staticmethod
    def _cognition_dimensions(visible: Mapping[str, Any]) -> tuple[tuple[str, ...], dict[str, Any], dict[str, Any]]:
        envelope = visible["request_envelopes"][0]
        options = envelope.get("options")
        if not isinstance(options, Mapping):
            raise ValueError("cognition intervention requires visible inference options")
        baseline_budget = options.get("num_predict", 128)
        if not isinstance(baseline_budget, int) or isinstance(baseline_budget, bool) or baseline_budget < 1:
            baseline_budget = 128
        target_budget = min(max(baseline_budget * 2, baseline_budget + 128), 4096)
        baseline_think = bool(envelope.get("think", False))
        dimensions = (
            "request_envelopes.0.think",
            "request_envelopes.0.options.num_predict",
        )
        target = {
            dimensions[0]: True,
            dimensions[1]: target_budget,
        }
        sham = {
            dimensions[0]: baseline_think,
            dimensions[1]: baseline_budget,
        }
        return dimensions, target, sham

    @staticmethod
    def _definition(
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        *,
        kind: InterventionKind,
        label: str,
        expected: str,
        changed_dimensions: tuple[str, ...] = (),
        overrides: Mapping[str, Any] | None = None,
        projected_physical_calls: int = 1,
        protected: bool | None = None,
    ) -> InterventionDefinition:
        return InterventionDefinition.create(
            hypothesis_id=hypothesis.hypothesis_id,
            failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            kind=kind,
            label=label,
            changed_dimensions=changed_dimensions,
            overrides={} if overrides is None else overrides,
            expected_causal_implication=expected,
            projected_physical_calls=projected_physical_calls,
            protected_exploration=(
                hypothesis.protected_exploration if protected is None else protected
            ),
        )

    @staticmethod
    def _sham(
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        target: InterventionDefinition,
        *,
        overrides: Mapping[str, Any],
    ) -> InterventionDefinition:
        return InterventionDefinition.create(
            hypothesis_id=hypothesis.hypothesis_id,
            failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            kind=InterventionKind.SHAM,
            label=f"matched control for {target.label}",
            changed_dimensions=target.changed_dimensions,
            overrides=overrides,
            expected_causal_implication=(
                "control should not reproduce the causal gain attributed to the targeted treatment"
            ),
            projected_physical_calls=target.projected_physical_calls,
            sham_for=target.intervention_id,
            protected_exploration=hypothesis.protected_exploration,
        )

    def _prompt_treatment(
        self,
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        visible: Mapping[str, Any],
        *,
        kind: InterventionKind,
        instruction: str,
        label: str,
    ) -> tuple[InterventionDefinition, InterventionDefinition]:
        path, original = self._message_dimension(visible)
        target = self._definition(
            fixture,
            hypothesis,
            kind=kind,
            label=label,
            changed_dimensions=(path,),
            overrides={path: f"{original}\n\n{instruction}"},
            expected=hypothesis.expected_if_true,
        )
        neutral = (
            f"{original}\n\nPreserve the original task, constraints, and answer process without "
            "adding a targeted repair mechanism."
        )
        return target, self._sham(fixture, hypothesis, target, overrides={path: neutral})

    def _for_hypothesis(
        self,
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        visible: Mapping[str, Any],
    ) -> tuple[InterventionDefinition, ...]:
        divergence = hypothesis.divergence.divergence_class
        owner = hypothesis.owner_candidate

        if divergence is DivergenceClass.CONTRACT_INTERFACE:
            if owner is ArchitectureOwner.SYSTEM:
                return (self._definition(
                    fixture,
                    hypothesis,
                    kind=InterventionKind.DETERMINISTIC,
                    label="deterministic contract formatter",
                    expected=hypothesis.expected_if_true,
                    projected_physical_calls=0,
                ),)
            return self._prompt_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.PROMPT,
                label="explicit contract preservation",
                instruction=(
                    "Before finalizing, enforce the stated output contract exactly; preserve the semantic "
                    "answer while correcting only contract/interface structure."
                ),
            )

        if divergence is DivergenceClass.INSUFFICIENT_REASONING:
            if owner is ArchitectureOwner.MODEL:
                dimensions, target_values, sham_values = self._cognition_dimensions(visible)
                target = self._definition(
                    fixture,
                    hypothesis,
                    kind=InterventionKind.COGNITION,
                    label="bounded reasoning budget increase",
                    changed_dimensions=dimensions,
                    overrides=target_values,
                    expected=hypothesis.expected_if_true,
                )
                return target, self._sham(
                    fixture,
                    hypothesis,
                    target,
                    overrides=sham_values,
                )
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.DETERMINISTIC,
                label="deterministic work reduction",
                expected=hypothesis.expected_if_true,
                projected_physical_calls=0,
            ),)

        if divergence is DivergenceClass.AUTHORITY_SCOPE:
            return self._prompt_treatment(
                fixture,
                hypothesis,
                visible,
                kind=(InterventionKind.CONTEXT if owner is ArchitectureOwner.SYSTEM else InterventionKind.PROMPT),
                label=("canonical authority and scope state" if owner is ArchitectureOwner.SYSTEM else "minimal authority clarification"),
                instruction=(
                    "Use only authority and scope explicitly present in the observable task state. "
                    "State the operative boundary before choosing an action and do not infer hidden authority."
                ),
            )

        if divergence is DivergenceClass.UNKNOWN_NOVEL and fixture.family == "ARITHMETIC":
            if owner is ArchitectureOwner.SYSTEM:
                return (self._definition(
                    fixture,
                    hypothesis,
                    kind=InterventionKind.DETERMINISTIC,
                    label="deterministic arithmetic substitute",
                    expected=hypothesis.expected_if_true,
                    projected_physical_calls=0,
                ),)
            dimensions, target_values, sham_values = self._cognition_dimensions(visible)
            target = self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.COGNITION,
                label="bounded task-local reasoning",
                changed_dimensions=dimensions,
                overrides=target_values,
                expected=hypothesis.expected_if_true,
            )
            return target, self._sham(
                fixture,
                hypothesis,
                target,
                overrides=sham_values,
            )

        return self._prompt_treatment(
            fixture,
            hypothesis,
            visible,
            kind=InterventionKind.PROMPT,
            label="protected hypothesis-separating probe",
            instruction=(
                "Identify the first observable uncertainty that blocks a confident answer, keep competing "
                "explanations separate, and resolve only what the visible evidence supports."
            ),
        )

    def generate(
        self,
        fixture: FailureFixture,
        report: AutopsyReport,
    ) -> tuple[InterventionDefinition, ...]:
        if not isinstance(fixture, FailureFixture):
            raise TypeError("fixture must be FailureFixture")
        if not isinstance(report, AutopsyReport):
            raise TypeError("report must be AutopsyReport")
        fixture = self._canonical_fixture(fixture)
        if report.failure_snapshot_id != fixture.failure_snapshot_id:
            raise ValueError("autopsy report failure lineage mismatch")
        visible = self._visible_payload(fixture)

        registered_hypotheses = {
            item.hypothesis_id: item
            for item in self.causal_store.hypotheses(fixture.failure_snapshot_id)
        }
        generated: list[InterventionDefinition] = []
        seen: set[str] = set()
        for hypothesis in report.hypotheses:
            current = registered_hypotheses.get(hypothesis.hypothesis_id)
            if current != hypothesis:
                raise ValueError("autopsy hypothesis is not registered in the causal evidence store")
            for intervention in self._for_hypothesis(fixture, hypothesis, visible):
                if intervention.intervention_id in seen:
                    continue
                self.causal_store.register_intervention(intervention)
                generated.append(intervention)
                seen.add(intervention.intervention_id)

        if not generated:
            raise ValueError("intervention generation produced no falsifiable treatment")
        if any("retry" in item.label.lower() for item in generated):
            raise ValueError("generic retry interventions are forbidden")
        return tuple(generated)
