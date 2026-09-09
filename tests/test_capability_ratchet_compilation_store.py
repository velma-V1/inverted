from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pytest

from inverted.capability_ratchet.compilation_core import (
    CompilationCandidate,
    CompilationDisposition,
    CompilationKind,
    CompilationPlan,
    CompiledCapability,
)
from inverted.capability_ratchet.compilation_store import CompilationEvidenceStore
from inverted.capability_ratchet.core import FailureFixture, Partition
from inverted.capability_ratchet.mutation_core import GeneralizationClass
from inverted.capability_ratchet.replay_store import ReplayStore


@dataclass(frozen=True)
class _Validation:
    ok: bool = True


@dataclass(frozen=True)
class _Profile:
    profile_id: str
    failure_snapshot_id: str
    mechanism_id: str
    classification: GeneralizationClass
    protected_failures: tuple[str, ...] = ()


class _MutationStore:
    def __init__(self, profile: _Profile) -> None:
        self._profile = profile

    def validate(self) -> _Validation:
        return _Validation()

    def profiles(self) -> tuple[_Profile, ...]:
        return (self._profile,)


class _CausalStore:
    def validate(self) -> _Validation:
        return _Validation()


def _replay_store(tmp_path) -> ReplayStore:
    store = ReplayStore(tmp_path / "replay")
    visible = store.put_asset({"messages": [{"role": "user", "content": "x"}]})
    failure = FailureFixture(
        failure_snapshot_id="failure-1",
        source_campaign_id="campaign-1",
        source_trial_id="trial-1",
        focus_observation_id="obs-1",
        focus_task_id="task-1",
        batch_task_ids=("task-1",),
        family="synthetic",
        failure_classes=("TOOL_SELECTION",),
        source_model_id="qwen-test",
        source_model_digest="digest-1",
        source_runtime={"runtime": "test"},
        inference_profile={"temperature": 0},
        inference_seed=1,
        partition=Partition.HISTORICAL,
        model_visible_asset_sha256=visible,
        state_hash="b" * 64,
        oracle_ref="oracle-1",
        expected_contract="answer",
        source_evidence_refs=("source-1",),
    )
    store.append(failure)
    assert store.validate().ok
    return store


def _candidate(*, mechanism_id="mechanism-1", payload=None) -> CompilationCandidate:
    return CompilationCandidate.create(
        failure_snapshot_id="failure-1",
        mechanism_id=mechanism_id,
        generalization_profile_id="profile-1",
        prior_generalized_evidence_ref=None,
        generalization_class=GeneralizationClass.REGION_MECHANISM,
        mechanism_label_ids=(f"label-{mechanism_id}",),
        evidence_refs=("result-1", "profile-1"),
        source_hashes={"profile-1": "a" * 64},
        supported_kinds=(CompilationKind.TOOL_POLICY,),
        excluded_cheaper_kinds={
            CompilationKind.DETERMINISTIC_RULE.value: "not deterministic",
            CompilationKind.STATE_REPRESENTATION.value: "state already complete",
            CompilationKind.FORMATTER_PARSER_VALIDATOR.value: "not a contract failure",
        },
        trigger_contract={"tool_eligible": True},
        compiled_payload={"allowed_tool": "calculator"} if payload is None else payload,
        verifier_contract={"postcondition": "result parses"},
        negative_transfer_boundary=("direct-solved cases stay direct",),
        tested_region="tool-eligible arithmetic region",
        rollback_action="DISABLE",
        partition=Partition.HISTORICAL,
        tomography_assessment_id="assessment-1",
    )


def _store(tmp_path, *, mechanism_id="mechanism-1") -> CompilationEvidenceStore:
    replay = _replay_store(tmp_path)
    mutation = _MutationStore(
        _Profile(
            profile_id="profile-1",
            failure_snapshot_id="failure-1",
            mechanism_id=mechanism_id,
            classification=GeneralizationClass.REGION_MECHANISM,
        )
    )
    return CompilationEvidenceStore(
        tmp_path / "compilation",
        replay_store=replay,
        mutation_store=mutation,
        causal_store=_CausalStore(),
    )


def _plan(candidate: CompilationCandidate) -> CompilationPlan:
    return CompilationPlan.create(
        candidate_id=candidate.candidate_id,
        selected_kind=CompilationKind.TOOL_POLICY,
        rejected_cheaper_kinds=candidate.excluded_cheaper_kinds,
        evidence_refs=candidate.evidence_refs,
        expected_disposition=CompilationDisposition.COMPILED,
    )


def _capability(candidate: CompilationCandidate, *, version=1, previous=None) -> CompiledCapability:
    return CompiledCapability.create(
        candidate=candidate,
        selected_kind=CompilationKind.TOOL_POLICY,
        version=version,
        previous_capability_id=previous,
        disposition=CompilationDisposition.COMPILED,
        handoff="STAGE10_OR_STAGE11",
    )


def test_append_candidate_decision_capability_and_validate(tmp_path) -> None:
    store = _store(tmp_path)
    candidate = _candidate()
    plan = _plan(candidate)
    capability = _capability(candidate)

    assert store.append_candidate(candidate) == candidate.candidate_id
    assert store.append_decision(plan) == plan.plan_id
    assert store.append_capability(capability) == capability.capability_id

    validation = store.validate()
    assert validation.ok
    assert validation.candidate_count == 1
    assert validation.decision_count == 1
    assert validation.capability_count == 1
    assert store.get_candidate(candidate.candidate_id) == candidate
    assert store.get_capability(capability.capability_id) == capability


def test_duplicate_identical_is_idempotent_and_changed_same_id_is_rejected(tmp_path) -> None:
    store = _store(tmp_path)
    candidate = _candidate()
    store.append_candidate(candidate)
    store.append_candidate(candidate)
    assert len(store.candidates()) == 1

    changed = _candidate(payload={"allowed_tool": "different"})
    object.__setattr__(changed, "candidate_id", candidate.candidate_id)
    with pytest.raises(ValueError, match="different canonical content|logical ID"):
        store.append_candidate(changed)


def test_store_rejects_broken_source_lineage_and_protected_partition(tmp_path) -> None:
    store = _store(tmp_path)
    wrong = _candidate(mechanism_id="different-mechanism")
    with pytest.raises(ValueError, match="profile|lineage|mechanism"):
        store.append_candidate(wrong)

    protected = _candidate()
    object.__setattr__(protected, "partition", Partition.FRESH)
    with pytest.raises(ValueError, match="FRESH|SEALED|protected"):
        store.append_candidate(protected)


def test_manifest_mismatch_blocks_append_and_validation_reports_it(tmp_path) -> None:
    store = _store(tmp_path)
    candidate = _candidate()
    store.append_candidate(candidate)
    store.manifest_path.write_text("corrupt\n", encoding="utf-8")
    assert not store.validate().ok
    assert store.validate().hash_mismatches
    with pytest.raises(ValueError, match="manifest|SHA256"):
        store.append_decision(_plan(candidate))


def test_version_chain_must_reference_existing_same_capability(tmp_path) -> None:
    store = _store(tmp_path)
    candidate = _candidate()
    store.append_candidate(candidate)
    store.append_decision(_plan(candidate))
    v1 = _capability(candidate)
    store.append_capability(v1)

    v2 = _capability(candidate, version=2, previous=v1.capability_id)
    store.append_capability(v2)
    assert store.capabilities() == (v1, v2)

    bad = _capability(candidate, version=2, previous="missing-capability")
    with pytest.raises(ValueError, match="previous|version"):
        store.append_capability(bad)


def test_raw_payload_duplication_is_rejected_even_if_object_is_tampered(tmp_path) -> None:
    store = _store(tmp_path)
    candidate = _candidate()
    object.__setattr__(candidate, "compiled_payload", {"raw_response": "secret-ish raw bytes"})
    with pytest.raises(ValueError, match="raw_response|raw model payload"):
        store.append_candidate(candidate)


def test_catalog_export_is_deterministic_and_empty_catalog_is_valid(tmp_path) -> None:
    empty = _store(tmp_path / "empty")
    empty_path = tmp_path / "empty.json"
    empty_catalog = empty.export_catalog(empty_path)
    assert empty_catalog["MODEL_CALLS"] == 0
    assert empty_catalog["capabilities"] == []
    assert len(empty_catalog["catalog_hash"]) == 64
    assert json.loads(empty_path.read_text(encoding="utf-8")) == empty_catalog

    first = _store(tmp_path / "first", mechanism_id="mechanism-1")
    c1 = _candidate(mechanism_id="mechanism-1")
    first.append_candidate(c1)
    first.append_decision(_plan(c1))
    first.append_capability(_capability(c1))

    # A second independent mechanism is represented with the same canonical failure/profile
    # shape but a distinct mechanism lineage in its own store, then the exported payloads are
    # compared after deterministic ordering.
    second = _store(tmp_path / "second", mechanism_id="mechanism-1")
    second.append_candidate(c1)
    second.append_decision(_plan(c1))
    second.append_capability(_capability(c1))

    out1 = first.export_catalog(tmp_path / "catalog-1.json")
    out2 = second.export_catalog(tmp_path / "catalog-2.json")
    assert out1 == out2
    body = {"MODEL_CALLS": 0, "capabilities": out1["capabilities"]}
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert out1["catalog_hash"] == expected
