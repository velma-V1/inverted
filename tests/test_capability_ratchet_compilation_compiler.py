from __future__ import annotations

import ast
from pathlib import Path

import pytest

from inverted.capability_ratchet.compilation_compiler import CapabilityCompiler
from inverted.capability_ratchet.compilation_core import (
    CompilationCandidate,
    CompilationDisposition,
    CompilationKind,
)
from inverted.capability_ratchet.compilation_planner import CompilationPlanner
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.mutation_core import GeneralizationClass


class _Validation:
    ok = True


class _Store:
    def __init__(self) -> None:
        self._candidates = []
        self._decisions = []
        self._capabilities = []

    def validate(self):
        return _Validation()

    def candidates(self):
        return tuple(self._candidates)

    def decisions(self):
        return tuple(self._decisions)

    def capabilities(self):
        return tuple(self._capabilities)

    def append_candidate(self, candidate):
        existing = [item for item in self._candidates if item.candidate_id == candidate.candidate_id]
        if not existing:
            self._candidates.append(candidate)
        elif existing[0] != candidate:
            raise ValueError("candidate logical ID collision")
        return candidate.candidate_id

    def append_decision(self, plan):
        existing = [item for item in self._decisions if item.plan_id == plan.plan_id]
        if not existing:
            self._decisions.append(plan)
        elif existing[0] != plan:
            raise ValueError("plan logical ID collision")
        return plan.plan_id

    def append_capability(self, capability):
        existing = [item for item in self._capabilities if item.capability_id == capability.capability_id]
        if not existing:
            self._capabilities.append(capability)
        elif existing[0] != capability:
            raise ValueError("capability logical ID collision")
        return capability.capability_id


def _candidate(*, payload=None, trigger=None, kind=CompilationKind.DETERMINISTIC_RULE, mechanism="mechanism-1"):
    return CompilationCandidate.create(
        failure_snapshot_id="failure-1",
        mechanism_id=mechanism,
        generalization_profile_id="profile-1",
        prior_generalized_evidence_ref=None,
        generalization_class=GeneralizationClass.REGION_MECHANISM,
        mechanism_label_ids=("label-1",),
        evidence_refs=("result-1", "profile-1"),
        source_hashes={"profile-1": "a" * 64},
        supported_kinds=(kind,),
        excluded_cheaper_kinds={
            cheaper.value: f"ruled out {cheaper.value}"
            for cheaper in CompilationPlanner().policy.owner_order
            if CompilationPlanner().policy.owner_order.index(cheaper)
            < CompilationPlanner().policy.owner_order.index(kind)
        },
        trigger_contract={"eligible": True} if trigger is None else trigger,
        compiled_payload={"action": "deterministic-transform"} if payload is None else payload,
        verifier_contract={"postcondition": "pass"},
        negative_transfer_boundary=("outside tested region",),
        tested_region="synthetic compiled region",
        rollback_action="DISABLE",
        partition=Partition.HISTORICAL,
        tomography_assessment_id="assessment-1",
        model_internal_residual=kind in {
            CompilationKind.FINE_TUNE_CANDIDATE,
            CompilationKind.ESCALATION_POLICY,
            CompilationKind.SAFE_STOP_BOUNDARY,
        },
    )


def _plan(candidate):
    return CompilationPlanner().plan(candidate)


def test_compile_version_one_preserves_evidence_and_cannot_deploy() -> None:
    store = _Store()
    compiler = CapabilityCompiler(store)
    candidate = _candidate()
    plan = _plan(candidate)

    capability = compiler.compile(candidate, plan)

    assert capability.version == 1
    assert capability.previous_capability_id is None
    assert capability.selected_kind is CompilationKind.DETERMINISTIC_RULE
    assert capability.disposition is CompilationDisposition.COMPILED
    assert capability.evidence_refs == candidate.evidence_refs
    assert capability.source_hashes == candidate.source_hashes
    assert capability.trigger_contract == candidate.trigger_contract
    assert capability.negative_transfer_boundary == candidate.negative_transfer_boundary
    assert capability.rollback_action == candidate.rollback_action
    assert capability.deployment_allowed is False
    assert capability.fresh_validation_required is True
    assert capability.handoff == "STAGE10_OR_STAGE11"
    assert store.candidates() == (candidate,)
    assert store.decisions() == (plan,)
    assert store.capabilities() == (capability,)


def test_new_candidate_version_keeps_capability_key_and_links_previous_immutably() -> None:
    store = _Store()
    compiler = CapabilityCompiler(store)
    first_candidate = _candidate(payload={"action": "v1"})
    first = compiler.compile(first_candidate, _plan(first_candidate))
    frozen_first = first

    second_candidate = _candidate(payload={"action": "v2"})
    second = compiler.compile(second_candidate, _plan(second_candidate))

    assert second.version == 2
    assert second.previous_capability_id == first.capability_id
    assert second.capability_key == first.capability_key
    assert first == frozen_first
    assert first.compiled_payload["action"] == "v1"
    assert second.compiled_payload["action"] == "v2"


def test_recompiling_identical_candidate_is_idempotent_not_a_new_version() -> None:
    store = _Store()
    compiler = CapabilityCompiler(store)
    candidate = _candidate()
    plan = _plan(candidate)
    first = compiler.compile(candidate, plan)
    second = compiler.compile(candidate, plan)
    assert second == first
    assert len(store.capabilities()) == 1


@pytest.mark.parametrize(
    ("kind", "expected_disposition", "handoff"),
    [
        (CompilationKind.TOOL_POLICY, CompilationDisposition.COMPILED, "STAGE10_OR_STAGE11"),
        (CompilationKind.SKILL_POLICY, CompilationDisposition.COMPILED, "STAGE10_OR_STAGE11"),
        (CompilationKind.VERIFIER_RECOVERY_POLICY, CompilationDisposition.COMPILED, "STAGE10_OR_STAGE11"),
        (CompilationKind.FINE_TUNE_CANDIDATE, CompilationDisposition.FINE_TUNE_CANDIDATE, "STAGE9"),
        (CompilationKind.ESCALATION_POLICY, CompilationDisposition.ESCALATION_CANDIDATE, "ESCALATION_POLICY_RESEARCH"),
        (CompilationKind.SAFE_STOP_BOUNDARY, CompilationDisposition.SAFE_STOP_BOUNDARY, "STAGE11_BOUNDARY_CONFIRMATION"),
    ],
)
def test_owner_specific_handoffs_are_explicit(kind, expected_disposition, handoff) -> None:
    store = _Store()
    candidate = _candidate(kind=kind)
    capability = CapabilityCompiler(store).compile(candidate, _plan(candidate))
    assert capability.selected_kind is kind
    assert capability.disposition is expected_disposition
    assert capability.handoff == handoff


def test_compiler_rejects_plan_that_does_not_match_candidate() -> None:
    store = _Store()
    first = _candidate(mechanism="mechanism-1")
    second = _candidate(mechanism="mechanism-2")
    with pytest.raises(ValueError, match="candidate|plan"):
        CapabilityCompiler(store).compile(first, _plan(second))


def test_compiler_rejects_tampered_hidden_oracle_trigger_and_raw_payload() -> None:
    compiler = CapabilityCompiler(_Store())
    candidate = _candidate()
    object.__setattr__(candidate, "trigger_contract", {"oracle_answer": "hidden"})
    with pytest.raises(ValueError, match="oracle|trigger"):
        compiler.compile(candidate, _plan(_candidate()))

    candidate = _candidate()
    object.__setattr__(candidate, "compiled_payload", {"raw_response": "duplicated raw output"})
    with pytest.raises(ValueError, match="raw_response|raw model payload"):
        compiler.compile(candidate, _plan(_candidate()))


def test_compiler_refuses_invalid_store_before_writing() -> None:
    store = _Store()
    store.validate = lambda: type("Bad", (), {"ok": False})()
    candidate = _candidate()
    with pytest.raises(ValueError, match="integrity|store"):
        CapabilityCompiler(store).compile(candidate, _plan(candidate))
    assert store.capabilities() == ()


def test_compiler_source_has_no_executor_or_network_transport_imports() -> None:
    source = Path("src/inverted/capability_ratchet/compilation_compiler.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"httpx", "requests", "socket", "urllib", "aiohttp"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports.isdisjoint(forbidden)
    assert "ReplayExecutor" not in source
    assert "Ollama" not in source
