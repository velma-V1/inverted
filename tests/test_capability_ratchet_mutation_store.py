from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from inverted.capability_ratchet.causal_core import MechanismRole
from inverted.capability_ratchet.core import (
    FailureFixture,
    MechanismLabel,
    MutationFixture,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.mutation_core import (
    GeneralizationClass,
    GeneralizationProfile,
    MutationAxis,
    MutationDirection,
    MutationOrigin,
    MutationPolicy,
    MutationSpec,
)
from inverted.capability_ratchet.mutation_store import (
    MutationEvidenceStore,
    MutationOutcome,
    MutationStudy,
)
from inverted.capability_ratchet.replay_store import ReplayStore


class SurfaceStub:
    def __init__(self, profiles=()):
        self._profiles = tuple(profiles)

    def profiles(self, mechanism_id=None):
        if mechanism_id is None:
            return self._profiles
        return tuple(item for item in self._profiles if item.mechanism_id == mechanism_id)

    def validate(self):
        return SimpleNamespace(ok=True)


def _failure(store: ReplayStore, *, partition=Partition.DEVELOPMENT):
    visible = store.put_asset({"task": {"depth": 2}})
    fixture = FailureFixture(
        failure_snapshot_id="failure-root",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0},
        inference_seed=3,
        partition=partition,
        model_visible_asset_sha256=visible,
        state_hash="a" * 64,
        oracle_ref="oracle",
        expected_contract="answer",
        source_evidence_refs=("source:1",),
    )
    store.append(fixture)
    return fixture


def _result(store: ReplayStore, source: FailureFixture, *, mutation_fixture_id=None, result_id="result-base"):
    metadata = {} if mutation_fixture_id is None else {"mutation_fixture_id": mutation_fixture_id}
    changed = ("repair",) if mutation_fixture_id is None else ("mutation_fixture_id",)
    override_value = True if mutation_fixture_id is None else mutation_fixture_id
    request = ReplayRequest(
        replay_request_id=f"request-{result_id}",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        decision_id="D12",
        hypothesis_id="hypothesis-1",
        expected_causal_implication="registered repair succeeds",
        mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=source.source_model_id,
        source_model_digest=source.source_model_digest,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        changed_dimensions=changed,
        intervention_id="intervention-1",
        overrides={changed[0]: override_value},
        metadata=metadata,
    )
    store.append(request)
    output_sha = store.put_asset({"answer": "ok"})
    raw_sha = store.put_asset({"request": request.replay_request_id, "response": "ok"})
    result = ReplayResult(
        replay_result_id=result_id,
        replay_request_id=request.replay_request_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mode=request.mode,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        completed=True,
        semantic_pass=True,
        contract_pass=True,
        output_asset_sha256=output_sha,
        raw_call_asset_sha256=raw_sha,
        metadata=metadata,
    )
    store.append(result)
    return result


def _movement(store: ReplayStore, source: FailureFixture):
    result = _result(store, source)
    label = MechanismLabel(
        mechanism_label_id="label-1",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="mechanism-1",
        hypothesis_id="hypothesis-1",
        intervention_ids=("intervention-1",),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(result.replay_result_id,),
        confidence=1.0,
    )
    store.append(label)
    event = PromotionEvent(
        promotion_event_id="promotion-movement",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=label.mechanism_id,
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="causal repair demonstrated",
        evidence_replay_result_ids=(result.replay_result_id,),
        partition=source.partition,
    )
    store.append(event)
    assert store.validate().ok
    return label


def _spec(*, protected=False):
    return MutationSpec(
        axis=MutationAxis.DEPENDENCY_DEPTH,
        direction=MutationDirection.HARDER,
        value=4,
        structural_region_id="planning/dependency",
        decision_id="D12",
        protected=protected,
    )


def _study(source: FailureFixture, *, decision_reason=None, profile_id=None, synthetic=True):
    spec = _spec(protected=True)
    return MutationStudy(
        study_id="mutation-study-1",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id="mechanism-1",
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        operating_surface_profile_id=profile_id,
        policy=MutationPolicy(),
        decision_id="D12",
        candidate_specs=(spec,),
        protected_spec_ids=(spec.spec_id,),
        decision_critical_reason=decision_reason,
        synthetic=synthetic,
    )


def _mutation(store: ReplayStore, source: FailureFixture, *, protected=True):
    visible = store.put_asset({"task": {"depth": 4}})
    oracle = store.put_asset({"answer": "ok"})
    fixture = MutationFixture.create(
        failure_snapshot_id=source.failure_snapshot_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        mechanism_id="mechanism-1",
        mutation_axis=MutationAxis.DEPENDENCY_DEPTH,
        mutation_direction=MutationDirection.HARDER,
        mutation_value=4,
        structural_region_id="planning/dependency",
        model_visible_asset_sha256=visible,
        oracle_asset_sha256=oracle,
        semantic_contract_hash="d" * 64,
        partition=source.partition,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD if source.partition not in {Partition.FRESH, Partition.SEALED} else MutationOrigin.NATURAL_OBSERVATION,
        metadata={"protected": protected, "mutation_spec_id": _spec(protected=protected).spec_id},
    )
    store.append(fixture)
    return fixture


def _outcome(store: ReplayStore, study: MutationStudy, fixture: MutationFixture):
    result = _result(
        store,
        store.get_failure(study.source_failure_snapshot_id),
        mutation_fixture_id=fixture.mutation_fixture_id,
        result_id="result-mutation",
    )
    return MutationOutcome(
        outcome_id="mutation-outcome-1",
        study_id=study.study_id,
        mutation_fixture_id=fixture.mutation_fixture_id,
        replay_result_id=result.replay_result_id,
        axis=fixture.mutation_axis,
        direction=fixture.mutation_direction,
        structural_region_id=fixture.structural_region_id,
        protected=bool(fixture.metadata.get("protected")),
        semantic_pass=result.semantic_pass,
        contract_pass=result.contract_pass,
        metadata={"boundary": "harder"},
    )


def _profile(study: MutationStudy, outcome: MutationOutcome):
    return GeneralizationProfile(
        profile_id="generalization-profile-1",
        study_id=study.study_id,
        failure_snapshot_id=study.failure_snapshot_id,
        mechanism_id=study.mechanism_id,
        policy=study.policy,
        mutation_result_ids=(outcome.replay_result_id,),
        successful_mutation_fixture_ids=(outcome.mutation_fixture_id,),
        failed_mutation_fixture_ids=(),
        axis_successes={outcome.axis.value: 1},
        region_successes={outcome.structural_region_id: 1},
        harder_successes=1,
        success_rate=1.0,
        protected_failures=(),
        classification=GeneralizationClass.INSTANCE_PATCH,
        unresolved_boundaries=(),
    )


def test_study_requires_movement_surface_profile_or_decision_critical_reason(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    with pytest.raises(ValueError, match="MOVEMENT|surface|decision-critical"):
        store.append_study(_study(source))

    accepted = _study(source, decision_reason="D12 remains unresolved at harder dependency depth")
    assert store.append_study(accepted) == accepted.study_id


def test_study_accepts_canonical_movement_mechanism(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    _movement(replay, source)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    study = _study(source)
    assert store.append_study(study) == study.study_id
    assert store.validate().ok


def test_study_accepts_matching_stage5_profile_without_relabeling_it(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    surface_profile = SimpleNamespace(
        profile_id="surface-profile-1",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id="mechanism-1",
    )
    surface = SurfaceStub((surface_profile,))
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=surface)
    study = _study(source, profile_id=surface_profile.profile_id)
    assert store.append_study(study) == study.study_id
    assert surface_profile.profile_id == "surface-profile-1"


def test_append_is_idempotent_but_logical_id_rewrite_is_rejected(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    _movement(replay, source)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    study = _study(source)
    store.append_study(study)
    before = store.study_path.read_bytes()
    store.append_study(study)
    assert store.study_path.read_bytes() == before

    changed = replace(study, decision_id="D11")
    with pytest.raises(ValueError, match="logical ID"):
        store.append_study(changed)


def test_validate_detects_manifest_tampering(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    _movement(replay, source)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    store.append_study(_study(source))
    store.study_manifest_path.write_text("0" * 64 + "\n", encoding="ascii")
    report = store.validate()
    assert not report.ok
    assert "mutation-studies.sha256" in report.hash_mismatches


def test_outcome_requires_stored_mutation_and_matching_replay_result(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    _movement(replay, source)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    study = _study(source)
    store.append_study(study)
    fixture = _mutation(replay, source)
    outcome = _outcome(replay, study, fixture)
    assert store.append_outcome(outcome) == outcome.outcome_id
    assert store.validate().ok

    missing = replace(outcome, outcome_id="outcome-missing", mutation_fixture_id="missing-fixture")
    with pytest.raises(ValueError, match="mutation fixture"):
        store.append_outcome(missing)

    mismatch = replace(outcome, outcome_id="outcome-wrong-result", replay_result_id="result-base")
    with pytest.raises(ValueError, match="matching|mutation"):
        store.append_outcome(mismatch)


def test_profile_evidence_must_resolve_to_stored_outcomes(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    _movement(replay, source)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    study = _study(source)
    store.append_study(study)
    fixture = _mutation(replay, source)
    outcome = _outcome(replay, study, fixture)
    store.append_outcome(outcome)
    profile = _profile(study, outcome)
    assert store.append_profile(profile) == profile.profile_id
    assert store.validate().ok

    bad = replace(profile, profile_id="profile-bad", mutation_result_ids=("missing-result",))
    with pytest.raises(ValueError, match="outcome|result"):
        store.append_profile(bad)


def test_synthetic_study_rejects_fresh_or_sealed_but_natural_observation_preserves_partition(tmp_path):
    for partition in (Partition.FRESH, Partition.SEALED):
        replay = ReplayStore(tmp_path / partition.value / "replay")
        source = _failure(replay, partition=partition)
        store = MutationEvidenceStore(
            tmp_path / partition.value / "mutation",
            replay_store=replay,
            surface_store=SurfaceStub(),
        )
        with pytest.raises(ValueError, match="synthetic|FRESH|SEALED"):
            store.append_study(
                _study(source, decision_reason="observe untouched transfer", synthetic=True)
            )
        natural = _study(
            source,
            decision_reason="record naturally observed transfer without development use",
            synthetic=False,
        )
        store.append_study(natural)
        assert replay.get_failure(source.failure_snapshot_id).partition is partition


def test_stage6_metadata_rejects_raw_model_payload_fields(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    source = _failure(replay)
    _movement(replay, source)
    store = MutationEvidenceStore(tmp_path / "mutation", replay_store=replay, surface_store=SurfaceStub())
    study = _study(source)
    store.append_study(study)
    fixture = _mutation(replay, source)
    outcome = _outcome(replay, study, fixture)
    contaminated = replace(outcome, metadata={"raw_response": "do not duplicate this"})
    with pytest.raises(ValueError, match="raw model|raw_response"):
        store.append_outcome(contaminated)
