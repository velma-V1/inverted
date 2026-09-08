"""Deterministic first-divergence autopsy for immutable V3 failure fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
)
from .causal_store import CausalEvidenceStore
from .core import FailureFixture, to_payload
from .replay_store import ReplayStore


@dataclass(frozen=True)
class AutopsyReport:
    failure_snapshot_id: str
    first_divergence: FirstDivergence
    hypotheses: tuple[CausalHypothesis, ...]
    evidence_refs: tuple[str, ...]
    unresolved_questions: tuple[str, ...] = ()


class HypothesisGenerator(Protocol):
    def generate(
        self,
        fixture: FailureFixture,
        divergence: FirstDivergence,
        observation: Mapping[str, Any],
    ) -> tuple[CausalHypothesis, ...]: ...


def _hypothesis(
    fixture: FailureFixture,
    divergence: FirstDivergence,
    *,
    owner: ArchitectureOwner,
    claim: str,
    expected: str,
    falsifier: str,
    protected: bool = False,
) -> CausalHypothesis:
    return CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=divergence,
        owner_candidate=owner,
        claim=claim,
        expected_if_true=expected,
        falsifier=falsifier,
        protected_exploration=protected,
    )


def _scientific_fixture_payload(fixture: FailureFixture) -> dict[str, Any]:
    payload = to_payload(fixture)
    payload.pop("record_id", None)
    return payload


_STAGE7_OWNERS = {
    DivergenceClass.TOOL_CAPABILITY: ArchitectureOwner.TOOL,
    DivergenceClass.TOOL_SELECTION: ArchitectureOwner.TOOL,
    DivergenceClass.TOOL_ARGUMENTS: ArchitectureOwner.TOOL,
    DivergenceClass.TOOL_INTERPRETATION: ArchitectureOwner.TOOL,
    DivergenceClass.VERIFIER_FEEDBACK: ArchitectureOwner.VERIFIER,
    DivergenceClass.RECOVERY_POLICY: ArchitectureOwner.RECOVERY,
    DivergenceClass.SKILL_DEFICIT: ArchitectureOwner.SKILL,
    DivergenceClass.MODEL_CAPABILITY_LIMIT: ArchitectureOwner.MODEL,
}


class DeterministicHypothesisGenerator:
    """Generate a small, falsifiable set from observable failure evidence only."""

    def generate(
        self,
        fixture: FailureFixture,
        divergence: FirstDivergence,
        observation: Mapping[str, Any],
    ) -> tuple[CausalHypothesis, ...]:
        kind = divergence.divergence_class
        hypotheses: list[CausalHypothesis] = []

        if kind in _STAGE7_OWNERS:
            owner = _STAGE7_OWNERS[kind]
            claims = {
                DivergenceClass.TOOL_CAPABILITY: (
                    "the residual failure is caused by missing required tool capability rather than model cognition",
                    "making only the required tool capability available repairs the frozen parent state",
                    "tool availability does not outperform the matched same-state control",
                ),
                DivergenceClass.TOOL_SELECTION: (
                    "the required tool is visible but the model fails at tool selection",
                    "forcing only the correct tool selection repairs the frozen parent state",
                    "forced correct selection does not beat neutral tool availability",
                ),
                DivergenceClass.TOOL_ARGUMENTS: (
                    "the required tool is selected but argument construction is the first observable failure",
                    "correcting only registered tool arguments repairs the frozen parent state",
                    "argument correction does not change the same-state outcome",
                ),
                DivergenceClass.TOOL_INTERPRETATION: (
                    "a correct deterministic tool result is available but result interpretation is the first observable failure",
                    "holding tool, arguments, and result fixed while correcting result-use repairs the state",
                    "result-use treatment fails despite fixed deterministic tool evidence",
                ),
                DivergenceClass.VERIFIER_FEEDBACK: (
                    "the error is deterministically verifier-detectable and recoverable from explicit verifier feedback",
                    "deterministic verifier feedback repairs the state while a matched sham does not",
                    "verifier and sham have the same outcome or verifier feedback does not repair the state",
                ),
                DivergenceClass.RECOVERY_POLICY: (
                    "a targeted correction keyed to the first diagnosed failure is more useful than another generic retry",
                    "targeted recovery repairs the state while a matched generic retry control fails",
                    "targeted recovery does not beat the matched generic retry control",
                ),
                DivergenceClass.SKILL_DEFICIT: (
                    "the residual is a reusable procedural deficit rather than one-off prompt sensitivity",
                    "a versioned skill procedure repairs structurally related cases without protected negative transfer",
                    "the procedure fails related cases, depends on incidental wording, or regresses protected cases",
                ),
                DivergenceClass.MODEL_CAPABILITY_LIMIT: (
                    "admissible external supports are exhausted and the remaining residual is model-internal",
                    "registered tool, skill, verifier, and targeted recovery supports fail to move the same state",
                    "any admissible external support causally repairs the residual",
                ),
            }
            claim, expected, falsifier = claims[kind]
            hypotheses.append(_hypothesis(
                fixture,
                divergence,
                owner=owner,
                claim=claim,
                expected=expected,
                falsifier=falsifier,
                protected=(kind is DivergenceClass.MODEL_CAPABILITY_LIMIT),
            ))

        elif kind is DivergenceClass.CONTRACT_INTERFACE:
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.SYSTEM,
                claim="the observed failure is a contract/interface defect separable from semantic cognition",
                expected="a deterministic formatter or explicit contract treatment repairs the contract while preserving semantic content",
                falsifier="the same-state contract treatment fails while a cognition-only treatment repairs the contract",
            ))
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.MODEL,
                claim="the model did not reliably preserve the required output contract",
                expected="an explicit contract-focused request repairs the same parent state",
                falsifier="contract-focused wording has no effect while deterministic formatting repairs the state",
            ))

        elif kind is DivergenceClass.INSUFFICIENT_REASONING:
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.MODEL,
                claim="the observed completion boundary truncated a still-live reasoning process",
                expected="a bounded reasoning-budget increase crosses the same-state completion boundary",
                falsifier="bounded additional reasoning does not repair the same parent state",
            ))
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.SYSTEM,
                claim="the failure may be avoidable by reducing model-owned work before the reasoning cap",
                expected="a smaller deterministic decomposition removes the cap-sensitive step",
                falsifier="decomposition leaves the same completion failure unchanged",
            ))

        elif kind is DivergenceClass.MISSING_DEPENDENCY:
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.SYSTEM,
                claim="the observed failure is caused by an absent explicit dependency-state representation",
                expected="an explicit prerequisite and dependency-order representation repairs the same parent state while its matched sham does not",
                falsifier="the dependency representation fails to beat its matched same-state sham",
            ))
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.MODEL,
                claim="the model failed to preserve or infer the visible prerequisite ordering without an explicit dependency representation",
                expected="making the dependency order explicit repairs the same parent state",
                falsifier="the explicit dependency order does not repair the same state or an equally shaped sham repairs it too",
            ))

        elif kind is DivergenceClass.AUTHORITY_SCOPE:
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.SYSTEM,
                claim="the failure originates in missing or misrepresented authority/scope state",
                expected="an explicit canonical authority/scope representation repairs the same parent state",
                falsifier="authority/scope representation does not change the same-state failure",
            ))
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.MODEL,
                claim="the model misinterpreted an observable authority boundary",
                expected="a minimal authority clarification repairs the same parent state",
                falsifier="clarification fails while a system-owned guard deterministically repairs the state",
            ))

        elif kind is DivergenceClass.UNKNOWN_NOVEL and fixture.family == "ARITHMETIC":
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.SYSTEM,
                claim="the failed arithmetic step may be removable from model ownership by deterministic computation",
                expected="a deterministic computation treatment repairs the same parent state without additional reasoning",
                falsifier="deterministic computation does not repair the same parent state",
            ))
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.MODEL,
                claim="the semantic arithmetic failure may reflect insufficient task-local reasoning rather than missing computation infrastructure",
                expected="a bounded reasoning treatment repairs the same parent state",
                falsifier="bounded reasoning does not repair the same parent state while deterministic computation does",
            ))

        else:
            hypotheses.append(_hypothesis(
                fixture, divergence, owner=ArchitectureOwner.MODEL,
                claim="the observed failure does not yet fit a supported causal mechanism",
                expected="a protected hypothesis-separating treatment changes the unresolved ownership decision",
                falsifier="registered protected alternatives fail to move the same parent state",
                protected=True,
            ))

        return tuple(hypotheses[:4])


class FailureAutopsy:
    def __init__(
        self,
        replay_store: ReplayStore,
        causal_store: CausalEvidenceStore,
        generator: HypothesisGenerator | None = None,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store
        self.generator = DeterministicHypothesisGenerator() if generator is None else generator

    def _forensic(self, fixture: FailureFixture) -> Mapping[str, Any]:
        if fixture.forensic_asset_sha256 is None:
            return {}
        payload = self.replay_store.read_asset(fixture.forensic_asset_sha256)
        if not isinstance(payload, Mapping):
            raise ValueError("forensic replay asset must be a mapping")
        return payload

    @staticmethod
    def _observation(fixture: FailureFixture, forensic: Mapping[str, Any]) -> Mapping[str, Any]:
        value = forensic.get("focus_observation")
        if isinstance(value, Mapping):
            return value
        return {
            "observation_id": fixture.focus_observation_id,
            "family": fixture.family,
            "semantic_pass": "SEMANTIC_FAIL" not in fixture.failure_classes,
            "contract_pass": "CONTRACT_FAIL" not in fixture.failure_classes,
            "completed": "COMPLETION_FAIL" not in fixture.failure_classes,
            "failure_classes": list(fixture.failure_classes),
        }

    @staticmethod
    def _done_reason(forensic: Mapping[str, Any]) -> str | None:
        trial = forensic.get("raw_trial")
        if not isinstance(trial, Mapping):
            return None
        calls = trial.get("raw_calls")
        if not isinstance(calls, list) or not calls or not isinstance(calls[0], Mapping):
            return None
        response = calls[0].get("response")
        if not isinstance(response, Mapping):
            return None
        value = response.get("done_reason")
        return value if isinstance(value, str) else None

    @staticmethod
    def _evidence_ref(fixture: FailureFixture, suffix: str) -> str:
        if fixture.forensic_asset_sha256 is None:
            return f"fixture:{fixture.failure_snapshot_id}:{suffix}"
        return f"forensic:{fixture.forensic_asset_sha256}:{suffix}"

    def _explicit_stage7_divergence(self, fixture: FailureFixture) -> FirstDivergence | None:
        evidence = fixture.metadata.get("stage7_evidence")
        if not isinstance(evidence, Mapping):
            return None
        explicit = evidence.get("divergence_class")
        if isinstance(explicit, str):
            try:
                kind = DivergenceClass(explicit)
            except ValueError:
                kind = None
            if kind in _STAGE7_OWNERS:
                return FirstDivergence(
                    divergence_class=kind,
                    observable_path="fixture.metadata.stage7_evidence.divergence_class",
                    event_index=0,
                    evidence_refs=(self._evidence_ref(fixture, "metadata.stage7_evidence"),),
                    confidence=1.0,
                )
        rules = (
            (bool(evidence.get("required_tool_absent")), DivergenceClass.TOOL_CAPABILITY, "required_tool_absent"),
            (evidence.get("tool_available") is True and evidence.get("tool_selected") is False, DivergenceClass.TOOL_SELECTION, "tool_selected"),
            (evidence.get("tool_selected_correct") is True and evidence.get("tool_arguments_correct") is False, DivergenceClass.TOOL_ARGUMENTS, "tool_arguments_correct"),
            (evidence.get("tool_result_available") is True and evidence.get("tool_result_interpreted_correctly") is False, DivergenceClass.TOOL_INTERPRETATION, "tool_result_interpreted_correctly"),
            (bool(evidence.get("verifier_would_detect")), DivergenceClass.VERIFIER_FEEDBACK, "verifier_would_detect"),
            (bool(evidence.get("targeted_recovery_defined")), DivergenceClass.RECOVERY_POLICY, "targeted_recovery_defined"),
            (bool(evidence.get("reusable_skill_required")), DivergenceClass.SKILL_DEFICIT, "reusable_skill_required"),
            (bool(evidence.get("external_supports_exhausted")), DivergenceClass.MODEL_CAPABILITY_LIMIT, "external_supports_exhausted"),
        )
        for matched, kind, key in rules:
            if matched:
                return FirstDivergence(
                    divergence_class=kind,
                    observable_path=f"fixture.metadata.stage7_evidence.{key}",
                    event_index=0,
                    evidence_refs=(self._evidence_ref(fixture, f"metadata.stage7_evidence.{key}"),),
                    confidence=1.0,
                )
        return None

    def _first_divergence(
        self,
        fixture: FailureFixture,
        observation: Mapping[str, Any],
        forensic: Mapping[str, Any],
    ) -> FirstDivergence:
        explicit_stage7 = self._explicit_stage7_divergence(fixture)
        if explicit_stage7 is not None:
            return explicit_stage7

        failures = set(fixture.failure_classes)
        observed_failures = observation.get("failure_classes")
        if isinstance(observed_failures, list):
            failures.update(item for item in observed_failures if isinstance(item, str))

        authority_flag = bool(fixture.metadata.get("authority_scope_error"))
        if "AUTHORITY_SCOPE" in failures or authority_flag:
            return FirstDivergence(
                divergence_class=DivergenceClass.AUTHORITY_SCOPE,
                observable_path="focus_observation.metadata.authority_scope_error",
                event_index=0,
                evidence_refs=(self._evidence_ref(fixture, "focus_observation.metadata"),),
                confidence=0.95,
            )

        dependency_flag = bool(fixture.metadata.get("dependency_state_missing"))
        if "MISSING_DEPENDENCY" in failures or dependency_flag:
            return FirstDivergence(
                divergence_class=DivergenceClass.MISSING_DEPENDENCY,
                observable_path=("focus_observation.metadata.dependency_state_missing" if dependency_flag else "focus_observation.failure_classes"),
                event_index=0,
                evidence_refs=(self._evidence_ref(fixture, "focus_observation.metadata.dependency_state_missing" if dependency_flag else "focus_observation.failure_classes"),),
                confidence=0.95,
            )

        done_reason = self._done_reason(forensic)
        if "REASONING_CAP_EXHAUSTION" in failures or (observation.get("completed") is False and done_reason == "length"):
            return FirstDivergence(
                divergence_class=DivergenceClass.INSUFFICIENT_REASONING,
                observable_path="raw_trial.raw_calls.0.response.done_reason",
                event_index=0,
                evidence_refs=(self._evidence_ref(fixture, "raw_trial.raw_calls.0.response.done_reason"),),
                confidence=0.95,
            )

        if observation.get("contract_pass") is False or "CONTRACT_FAIL" in failures:
            return FirstDivergence(
                divergence_class=DivergenceClass.CONTRACT_INTERFACE,
                observable_path="focus_observation.contract_pass",
                event_index=0,
                evidence_refs=(self._evidence_ref(fixture, "focus_observation.contract_pass"),),
                confidence=1.0,
            )

        if observation.get("semantic_pass") is False or "SEMANTIC_FAIL" in failures:
            return FirstDivergence(
                divergence_class=DivergenceClass.UNKNOWN_NOVEL,
                observable_path="focus_observation.semantic_pass",
                event_index=0,
                evidence_refs=(self._evidence_ref(fixture, "focus_observation.semantic_pass"),),
                confidence=0.5,
            )

        return FirstDivergence(
            divergence_class=DivergenceClass.UNKNOWN_NOVEL,
            observable_path="focus_observation.failure_classes",
            event_index=0,
            evidence_refs=(self._evidence_ref(fixture, "focus_observation.failure_classes"),),
            confidence=0.25,
        )

    def analyze(self, fixture: FailureFixture) -> AutopsyReport:
        if not isinstance(fixture, FailureFixture):
            raise TypeError("fixture must be FailureFixture")
        validation = self.replay_store.validate()
        if not validation.ok:
            raise ValueError("replay store integrity validation failed")
        current = self.replay_store.get_failure(fixture.failure_snapshot_id)
        if _scientific_fixture_payload(current) != _scientific_fixture_payload(fixture):
            raise ValueError("autopsy fixture is not the active canonical replay failure")
        fixture = current

        forensic = self._forensic(fixture)
        observation = self._observation(fixture, forensic)
        divergence = self._first_divergence(fixture, observation, forensic)
        hypotheses = tuple(self.generator.generate(fixture, divergence, observation))
        if not hypotheses or len(hypotheses) > 4:
            raise ValueError("autopsy must produce between one and four live hypotheses")
        for hypothesis in hypotheses:
            if hypothesis.failure_snapshot_id != fixture.failure_snapshot_id:
                raise ValueError("hypothesis failure lineage mismatch")
            if hypothesis.parent_state_hash != fixture.state_hash:
                raise ValueError("hypothesis parent state mismatch")
            self.causal_store.append_hypothesis(hypothesis)

        unresolved: tuple[str, ...] = ()
        if divergence.divergence_class is DivergenceClass.UNKNOWN_NOVEL and fixture.family != "ARITHMETIC":
            unresolved = ("which safely observable state transition first separates this failure from nearby successes?",)
        evidence_refs = tuple(dict.fromkeys(ref for hypothesis in hypotheses for ref in hypothesis.divergence.evidence_refs))
        return AutopsyReport(
            failure_snapshot_id=fixture.failure_snapshot_id,
            first_divergence=divergence,
            hypotheses=hypotheses,
            evidence_refs=evidence_refs,
            unresolved_questions=unresolved,
        )
