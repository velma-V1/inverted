"""Deterministic hypothesis-to-intervention generation for V3 failure research."""

from __future__ import annotations

import json
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
from .core import FailureFixture, ReplayMode, ReplayRequest, to_payload
from .replay_store import ReplayStore


def _scientific_fixture_payload(fixture: FailureFixture) -> dict[str, Any]:
    payload = to_payload(fixture)
    payload.pop("record_id", None)
    return payload


def _plain_json(value: Any) -> Any:
    """Normalize frozen scientific metadata into finite JSON-compatible values."""
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Stage-7 evidence must contain finite JSON data") from exc
    return value


class InterventionGenerator:
    """Compile one registered causal hypothesis into falsifiable treatments.

    Only canonical model-visible replay assets are used to construct model-visible
    overrides. Forensic/oracle material is deliberately outside this class.
    """

    def __init__(self, replay_store: ReplayStore, causal_store: CausalEvidenceStore) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store

    def _canonical_fixture(self, fixture: FailureFixture) -> FailureFixture:
        if not isinstance(fixture, FailureFixture):
            raise TypeError("fixture must be FailureFixture")
        validation = self.replay_store.validate()
        if not validation.ok:
            raise ValueError("replay store integrity validation failed")
        current = self.replay_store.get_failure(fixture.failure_snapshot_id)
        if _scientific_fixture_payload(current) != _scientific_fixture_payload(fixture):
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
    def _tool_dimension(visible: Mapping[str, Any]) -> tuple[str, list[Any]]:
        envelope = visible["request_envelopes"][0]
        if "tools" not in envelope:
            raise ValueError("tool intervention requires an explicit visible tools leaf")
        tools = envelope.get("tools")
        if not isinstance(tools, list):
            raise ValueError("tool intervention requires visible tools to be a list")
        return "request_envelopes.0.tools", list(tools)

    @staticmethod
    def _stage7_evidence(fixture: FailureFixture) -> Mapping[str, Any]:
        evidence = fixture.metadata.get("stage7_evidence")
        if not isinstance(evidence, Mapping):
            raise ValueError("Stage-7 intervention requires explicit observable stage7_evidence")
        return evidence

    @staticmethod
    def _required_text(evidence: Mapping[str, Any], key: str) -> str:
        value = evidence.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Stage-7 intervention requires non-blank {key}")
        return value

    @staticmethod
    def _tool_name(tool: Any) -> str | None:
        if not isinstance(tool, Mapping):
            return None
        function = tool.get("function")
        if isinstance(function, Mapping) and isinstance(function.get("name"), str):
            return function["name"]
        value = tool.get("name")
        return value if isinstance(value, str) else None

    @staticmethod
    def _json_text(value: Any, *, name: str) -> str:
        try:
            return json.dumps(
                _plain_json(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite JSON data") from exc

    @staticmethod
    def _cognition_dimensions(
        visible: Mapping[str, Any],
    ) -> tuple[tuple[str, ...], dict[str, Any]]:
        envelope = visible["request_envelopes"][0]
        options = envelope.get("options")
        if not isinstance(options, Mapping):
            raise ValueError("cognition intervention requires visible inference options")
        baseline_budget = options.get("num_predict", 128)
        if not isinstance(baseline_budget, int) or isinstance(baseline_budget, bool) or baseline_budget < 1:
            baseline_budget = 128
        target_budget = min(max(baseline_budget * 2, baseline_budget + 128), 4096)
        dimensions = (
            "request_envelopes.0.think",
            "request_envelopes.0.options.num_predict",
        )
        return dimensions, {dimensions[0]: True, dimensions[1]: target_budget}

    @staticmethod
    def _definition(
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        *,
        kind: InterventionKind,
        label: str,
        changed_dimensions: tuple[str, ...] = (),
        overrides: Mapping[str, Any] | None = None,
        projected_physical_calls: int = 1,
    ) -> InterventionDefinition:
        return InterventionDefinition.create(
            hypothesis_id=hypothesis.hypothesis_id,
            failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            kind=kind,
            label=label,
            changed_dimensions=changed_dimensions,
            overrides={} if overrides is None else _plain_json(overrides),
            expected_causal_implication=hypothesis.expected_if_true,
            projected_physical_calls=projected_physical_calls,
            protected_exploration=hypothesis.protected_exploration,
        )

    def _message_treatment(
        self,
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        visible: Mapping[str, Any],
        *,
        kind: InterventionKind,
        label: str,
        heading: str,
        instruction: str,
    ) -> InterventionDefinition:
        path, original = self._message_dimension(visible)
        return self._definition(
            fixture,
            hypothesis,
            kind=kind,
            label=label,
            changed_dimensions=(path,),
            overrides={path: f"{original}\n\n{heading}\n{instruction}"},
        )

    def _stage7_recipe(
        self,
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        visible: Mapping[str, Any],
    ) -> tuple[InterventionDefinition, ...] | None:
        divergence = hypothesis.divergence.divergence_class
        if divergence not in {
            DivergenceClass.TOOL_CAPABILITY,
            DivergenceClass.TOOL_SELECTION,
            DivergenceClass.TOOL_ARGUMENTS,
            DivergenceClass.TOOL_INTERPRETATION,
            DivergenceClass.VERIFIER_FEEDBACK,
            DivergenceClass.RECOVERY_POLICY,
            DivergenceClass.SKILL_DEFICIT,
            DivergenceClass.MODEL_CAPABILITY_LIMIT,
        }:
            return None

        evidence = self._stage7_evidence(fixture)

        if divergence is DivergenceClass.TOOL_CAPABILITY:
            path, current_tools = self._tool_dimension(visible)
            required = evidence.get("required_tool_schema")
            if not isinstance(required, Mapping):
                raise ValueError("TOOL_CAPABILITY requires required_tool_schema")
            required_plain = _plain_json(required)
            if required_plain in current_tools:
                raise ValueError("required tool is already present in visible tool state")
            tools = current_tools + [required_plain]
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.TOOL,
                label="supply required tool capability",
                changed_dimensions=(path,),
                overrides={path: tools},
            ),)

        if divergence is DivergenceClass.TOOL_SELECTION:
            path, current_tools = self._tool_dimension(visible)
            required_name = self._required_text(evidence, "required_tool_name")
            selected = [tool for tool in current_tools if self._tool_name(tool) == required_name]
            if len(selected) != 1:
                raise ValueError("TOOL_SELECTION requires exactly one visible matching required tool")
            if len(current_tools) == 1:
                raise ValueError("TOOL_SELECTION contrast requires a nontrivial visible tool menu")
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.TOOL,
                label="force correct tool selection",
                changed_dimensions=(path,),
                overrides={path: selected},
            ),)

        if divergence is DivergenceClass.TOOL_ARGUMENTS:
            tool_name = self._required_text(evidence, "required_tool_name")
            arguments = evidence.get("canonical_tool_arguments")
            if not isinstance(arguments, Mapping):
                raise ValueError("TOOL_ARGUMENTS requires canonical_tool_arguments")
            rendered = self._json_text(arguments, name="canonical_tool_arguments")
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.TOOL,
                label="supply registered canonical tool arguments",
                heading="REGISTERED TOOL ARGUMENTS",
                instruction=f"Use tool {tool_name!r} with exactly these registered arguments: {rendered}",
            ),)

        if divergence is DivergenceClass.TOOL_INTERPRETATION:
            tool_name = self._required_text(evidence, "required_tool_name")
            if "canonical_tool_result" not in evidence:
                raise ValueError("TOOL_INTERPRETATION requires canonical_tool_result")
            rendered = self._json_text(evidence["canonical_tool_result"], name="canonical_tool_result")
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.TOOL,
                label="supply registered canonical tool result for interpretation",
                heading="REGISTERED TOOL RESULT",
                instruction=(
                    f"Treat this preserved result from tool {tool_name!r} as the fixed tool evidence and derive the answer from it: {rendered}"
                ),
            ),)

        if divergence is DivergenceClass.VERIFIER_FEEDBACK:
            feedback = self._required_text(evidence, "verifier_feedback")
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.VERIFICATION_RECOVERY,
                label="deterministic verifier feedback",
                heading="VERIFIER FEEDBACK",
                instruction=f"Apply only this registered deterministic feedback, then re-check the affected postcondition: {feedback}",
            ),)

        if divergence is DivergenceClass.RECOVERY_POLICY:
            recovery = evidence.get("targeted_recovery")
            if not isinstance(recovery, Mapping):
                raise ValueError("RECOVERY_POLICY requires targeted_recovery mapping")
            changed_state = recovery.get("changed_state")
            instruction = recovery.get("instruction")
            if not isinstance(changed_state, str) or not changed_state.strip():
                raise ValueError("targeted_recovery requires explicit changed_state")
            if not isinstance(instruction, str) or not instruction.strip():
                raise ValueError("targeted_recovery requires explicit instruction")
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.VERIFICATION_RECOVERY,
                label="targeted state recovery",
                heading="TARGETED RECOVERY",
                instruction=f"Changed state: {changed_state}. Recovery action: {instruction}",
            ),)

        if divergence is DivergenceClass.SKILL_DEFICIT:
            skill_id = self._required_text(evidence, "skill_id")
            version = self._required_text(evidence, "skill_version")
            trigger = self._required_text(evidence, "skill_trigger")
            procedure = self._required_text(evidence, "skill_procedure")
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.SKILL,
                label=f"registered skill procedure {skill_id}@{version}",
                heading="REGISTERED SKILL",
                instruction=f"Trigger: {trigger}\nProcedure: {procedure}",
            ),)

        if divergence is DivergenceClass.MODEL_CAPABILITY_LIMIT:
            if evidence.get("external_supports_exhausted") is not True:
                raise ValueError("MODEL_CAPABILITY_LIMIT requires external_supports_exhausted=true")
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.ESCALATION,
                label="stronger-model escalation reference",
                projected_physical_calls=0,
            ),)

        raise AssertionError("unreachable Stage-7 divergence")

    def _recipe(
        self,
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
        visible: Mapping[str, Any],
    ) -> tuple[InterventionDefinition, ...]:
        divergence = hypothesis.divergence.divergence_class
        owner = hypothesis.owner_candidate

        stage7 = self._stage7_recipe(fixture, hypothesis, visible)
        if stage7 is not None:
            return stage7

        if divergence is DivergenceClass.CONTRACT_INTERFACE:
            if owner is ArchitectureOwner.SYSTEM:
                return (self._definition(
                    fixture,
                    hypothesis,
                    kind=InterventionKind.DETERMINISTIC,
                    label="deterministic contract formatter",
                    projected_physical_calls=0,
                ),)
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.PROMPT,
                label="explicit contract preservation",
                heading="CONTRACT CHECK",
                instruction=(
                    "Enforce the stated output contract exactly while preserving the semantic answer."
                ),
            ),)

        if divergence is DivergenceClass.INSUFFICIENT_REASONING:
            if owner is ArchitectureOwner.MODEL:
                dimensions, overrides = self._cognition_dimensions(visible)
                return (self._definition(
                    fixture,
                    hypothesis,
                    kind=InterventionKind.COGNITION,
                    label="bounded reasoning budget increase",
                    changed_dimensions=dimensions,
                    overrides=overrides,
                ),)
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.DETERMINISTIC,
                label="deterministic work reduction",
                projected_physical_calls=0,
            ),)

        if divergence is DivergenceClass.MISSING_DEPENDENCY:
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.REPRESENTATION,
                label="explicit dependency representation",
                heading="DEPENDENCY STATE",
                instruction=(
                    "Enumerate the visible prerequisites and dependency order before selecting the next action."
                ),
            ),)

        if divergence is DivergenceClass.MISSING_STATE:
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.CONTEXT,
                label="canonical observable state",
                heading="CANONICAL STATE",
                instruction=(
                    "Restate only the task state that is explicitly visible, then reason from that state without inventing missing facts."
                ),
            ),)

        if divergence is DivergenceClass.AUTHORITY_SCOPE:
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=(InterventionKind.CONTEXT if owner is ArchitectureOwner.SYSTEM else InterventionKind.PROMPT),
                label=("canonical authority and scope state" if owner is ArchitectureOwner.SYSTEM else "minimal authority clarification"),
                heading="AUTHORITY / SCOPE",
                instruction=(
                    "Use only authority explicitly present in the visible state; state the operative boundary before acting."
                ),
            ),)

        if divergence in {DivergenceClass.DETERMINISTIC_COMPUTATION} or (
            divergence is DivergenceClass.UNKNOWN_NOVEL
            and fixture.family == "ARITHMETIC"
            and owner is ArchitectureOwner.SYSTEM
        ):
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.DETERMINISTIC,
                label="deterministic computation substitute",
                projected_physical_calls=0,
            ),)

        if divergence is DivergenceClass.UNKNOWN_NOVEL and fixture.family == "ARITHMETIC":
            dimensions, overrides = self._cognition_dimensions(visible)
            return (self._definition(
                fixture,
                hypothesis,
                kind=InterventionKind.COGNITION,
                label="bounded task-local reasoning",
                changed_dimensions=dimensions,
                overrides=overrides,
            ),)

        if divergence in {
            DivergenceClass.EVIDENCE_FAILURE,
            DivergenceClass.AMBIGUITY,
            DivergenceClass.ACTION_SPACE,
            DivergenceClass.CONTEXT_PRESSURE,
        }:
            return (self._message_treatment(
                fixture,
                hypothesis,
                visible,
                kind=InterventionKind.CONTEXT,
                label="targeted observable-state clarification",
                heading="EVIDENCE BOUNDARY",
                instruction=(
                    "Separate known, missing, and contradictory visible evidence; resolve only what the available evidence supports."
                ),
            ),)

        return (self._message_treatment(
            fixture,
            hypothesis,
            visible,
            kind=InterventionKind.PROMPT,
            label="protected hypothesis-separating probe",
            heading="HYPOTHESIS-SEPARATING CHECK",
            instruction=(
                "Identify the first observable uncertainty blocking a confident answer, keep competing explanations separate, and resolve only visible evidence."
            ),
        ),)

    def generate(
        self,
        fixture: FailureFixture,
        hypothesis: CausalHypothesis,
    ) -> tuple[InterventionDefinition, ...]:
        fixture = self._canonical_fixture(fixture)
        if not isinstance(hypothesis, CausalHypothesis):
            raise TypeError("hypothesis must be CausalHypothesis")
        if hypothesis.failure_snapshot_id != fixture.failure_snapshot_id:
            raise ValueError("hypothesis failure lineage mismatch")
        if hypothesis.parent_state_hash != fixture.state_hash:
            raise ValueError("hypothesis parent state mismatch")
        registered = {
            item.hypothesis_id: item
            for item in self.causal_store.hypotheses(fixture.failure_snapshot_id)
        }
        if registered.get(hypothesis.hypothesis_id) != hypothesis:
            raise ValueError("hypothesis is not registered in the causal evidence store")

        visible = self._visible_payload(fixture)
        interventions = self._recipe(fixture, hypothesis, visible)
        if not interventions:
            raise ValueError("intervention generation produced no falsifiable treatment")
        for intervention in interventions:
            if "retry" in intervention.label.lower():
                raise ValueError("generic retry interventions are forbidden")
            self.causal_store.register_intervention(intervention)
        return interventions

    def make_matched_sham(
        self,
        target: InterventionDefinition,
    ) -> InterventionDefinition | None:
        if not isinstance(target, InterventionDefinition):
            raise TypeError("target must be InterventionDefinition")
        if target.projected_physical_calls == 0 or target.kind is InterventionKind.DETERMINISTIC:
            return None
        if not target.changed_dimensions:
            return None
        fixture = self.replay_store.get_failure(target.failure_snapshot_id)
        visible = self._visible_payload(fixture)
        hypothesis = {
            item.hypothesis_id: item
            for item in self.causal_store.hypotheses(fixture.failure_snapshot_id)
        }.get(target.hypothesis_id)
        if hypothesis is None:
            raise ValueError("target hypothesis is not registered")

        path = target.changed_dimensions[0]
        if path.endswith(".content"):
            _, original = self._message_dimension(visible)
            overrides = {
                path: (
                    f"{original}\n\nCONTROL CHECK\nPreserve the original task and response process without adding the targeted repair mechanism."
                )
            }
            # Multi-leaf treatments are cognition-only in Plan 2; message treatments use one leaf.
        else:
            envelope = visible["request_envelopes"][0]
            options = envelope.get("options", {})
            overrides = {}
            for dimension in target.changed_dimensions:
                if dimension.endswith(".think"):
                    overrides[dimension] = bool(envelope.get("think", False))
                elif ".options." in dimension:
                    key = dimension.rsplit(".", 1)[-1]
                    overrides[dimension] = options.get(key)
                elif dimension.endswith(".tools"):
                    if "tools" not in envelope or not isinstance(envelope.get("tools"), list):
                        raise ValueError("cannot construct matched tool sham without visible tools leaf")
                    overrides[dimension] = list(envelope["tools"])
                else:
                    raise ValueError(f"cannot construct matched sham for dimension {dimension}")

        sham = InterventionDefinition.create(
            hypothesis_id=target.hypothesis_id,
            failure_snapshot_id=target.failure_snapshot_id,
            parent_state_hash=target.parent_state_hash,
            kind=InterventionKind.SHAM,
            label=f"matched control for {target.label}",
            changed_dimensions=target.changed_dimensions,
            overrides=_plain_json(overrides),
            expected_causal_implication=(
                "the matched control should not reproduce gain caused by the targeted mechanism"
            ),
            projected_physical_calls=target.projected_physical_calls,
            sham_for=target.intervention_id,
            protected_exploration=hypothesis.protected_exploration,
        )
        self.causal_store.register_intervention(sham)
        return sham

    def _root_failure_id(self, fixture: FailureFixture) -> str:
        current = fixture
        seen: set[str] = set()
        while current.parent_failure_snapshot_id is not None:
            if current.failure_snapshot_id in seen:
                raise ValueError("failure lineage cycle")
            seen.add(current.failure_snapshot_id)
            current = self.replay_store.get_failure(current.parent_failure_snapshot_id)
        return current.failure_snapshot_id

    def compile_request(
        self,
        fixture: FailureFixture,
        intervention: InterventionDefinition,
        request_id: str,
        decision_id: str,
    ) -> ReplayRequest:
        fixture = self._canonical_fixture(fixture)
        if not isinstance(intervention, InterventionDefinition):
            raise TypeError("intervention must be InterventionDefinition")
        if intervention.failure_snapshot_id != fixture.failure_snapshot_id:
            raise ValueError("intervention failure lineage mismatch")
        if intervention.parent_state_hash != fixture.state_hash:
            raise ValueError("intervention parent state mismatch")
        registered = self.causal_store.get_intervention(intervention.intervention_id)
        if registered != intervention:
            raise ValueError("intervention is not the registered canonical treatment")
        if intervention.projected_physical_calls == 0 or intervention.kind is InterventionKind.DETERMINISTIC:
            raise ValueError("zero-model-call intervention cannot be compiled as a model replay")
        if not intervention.changed_dimensions:
            raise ValueError("model-visible intervention requires registered changed dimensions")

        return ReplayRequest(
            replay_request_id=request_id,
            failure_snapshot_id=self._root_failure_id(fixture),
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            decision_id=decision_id,
            hypothesis_id=intervention.hypothesis_id,
            expected_causal_implication=intervention.expected_causal_implication,
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest,
            target_model_id=fixture.source_model_id,
            target_model_digest=fixture.source_model_digest,
            partition=fixture.partition,
            changed_dimensions=intervention.changed_dimensions,
            intervention_id=intervention.intervention_id,
            overrides=intervention.overrides,
            metadata={
                "intervention_kind": intervention.kind.value,
                "projected_physical_calls": intervention.projected_physical_calls,
                "protected_exploration": intervention.protected_exploration,
            },
        )


class TailoredInterventionGenerator:
    """Compatibility facade that expands every hypothesis in one autopsy report."""

    def __init__(self, replay_store: ReplayStore, causal_store: CausalEvidenceStore) -> None:
        self.generator = InterventionGenerator(replay_store, causal_store)

    def generate(
        self,
        fixture: FailureFixture,
        report: AutopsyReport,
    ) -> tuple[InterventionDefinition, ...]:
        if not isinstance(report, AutopsyReport):
            raise TypeError("report must be AutopsyReport")
        if report.failure_snapshot_id != fixture.failure_snapshot_id:
            raise ValueError("autopsy report failure lineage mismatch")
        generated: list[InterventionDefinition] = []
        seen: set[str] = set()
        for hypothesis in report.hypotheses:
            for target in self.generator.generate(fixture, hypothesis):
                for intervention in (target, self.generator.make_matched_sham(target)):
                    if intervention is None or intervention.intervention_id in seen:
                        continue
                    generated.append(intervention)
                    seen.add(intervention.intervention_id)
        if not generated:
            raise ValueError("intervention generation produced no falsifiable treatment")
        return tuple(generated)
