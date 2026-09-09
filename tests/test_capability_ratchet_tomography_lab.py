from __future__ import annotations

from types import SimpleNamespace

import pytest

from inverted.capability_ratchet.causal_core import InterventionDefinition, InterventionKind
from inverted.capability_ratchet.core import FailureFixture, Partition, ReplayMode
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.tomography_core import (
    TomographyAxis,
    TomographyProbe,
    TomographyStatus,
    TomographyStudy,
)
from inverted.capability_ratchet.tomography_lab import TomographyLab
from inverted.capability_ratchet.tomography_store import TomographyEvidenceStore


SHA = "a" * 64
PATH = "request_envelopes.0.tool_result"


class FakeAdapter:
    def runtime_provenance(self):
        return {"provider": "fake", "model": "fake-model", "model_digest": "fake-digest"}


class RecordingExecutor:
    instances = []
    result = None

    def __init__(self, store, adapters):
        self.store = store
        self.adapters = adapters
        self.requests = []
        type(self).instances.append(self)

    def execute(self, request):
        self.requests.append(request)
        return type(self).result


def _fixture(replay: ReplayStore, *, partition=Partition.DEVELOPMENT):
    visible = {
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "num_predict": 64, "temperature": 0.0},
            "messages": [{"role": "user", "content": "BASE TASK"}],
        }],
        "task": {"kind": "stage7-lab"},
    }
    fixture = FailureFixture(
        failure_snapshot_id="failure-lab",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="TOOL_USE",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0},
        inference_seed=7,
        partition=partition,
        model_visible_asset_sha256=replay.put_asset(visible),
        state_hash=SHA,
        oracle_ref="oracle:stage7-lab",
        expected_contract="return a valid answer",
        source_evidence_refs=("evidence:stage7-lab",),
        oracle_asset_sha256=replay.put_asset({"answer": 42}),
    )
    replay.append(fixture)
    return replay.get_failure(fixture.failure_snapshot_id)


def _study(*, axis=TomographyAxis.TOOL_EXECUTION_RESULT, partition=Partition.DEVELOPMENT):
    return TomographyStudy(
        study_id="study-lab",
        failure_snapshot_id="failure-lab",
        parent_state_hash=SHA,
        partition=partition,
        decision_ids=("D6", "D8"),
        candidate_axes=(axis,),
        baseline_evidence_refs=("replay-baseline",),
        probe_ids=("probe-lab",),
        max_new_probes=3,
        projected_calls=1,
        status=TomographyStatus.PLANNED,
        stop_reason=None,
    )


def _probe(axis=TomographyAxis.TOOL_EXECUTION_RESULT):
    return TomographyProbe(
        probe_id="probe-lab",
        study_id="study-lab",
        axis=axis,
        intervention_id="int-placeholder",
        control_intervention_id=None,
        changed_dimensions=(PATH,),
        expected_implication="isolate the Stage-7 owner",
        projected_calls=1,
        protected=False,
    )


def _intervention(study, probe):
    intervention = InterventionDefinition.create(
        hypothesis_id="hyp-lab",
        failure_snapshot_id=study.failure_snapshot_id,
        parent_state_hash=study.parent_state_hash,
        kind=InterventionKind.TOOL,
        label="canonical Stage-7 intervention",
        changed_dimensions=probe.changed_dimensions,
        overrides={PATH: {"status": "ok", "value": 42}},
        expected_causal_implication=probe.expected_implication,
    )
    return TomographyProbe(
        probe_id=probe.probe_id,
        study_id=probe.study_id,
        axis=probe.axis,
        intervention_id=intervention.intervention_id,
        control_intervention_id=probe.control_intervention_id,
        changed_dimensions=probe.changed_dimensions,
        expected_implication=probe.expected_implication,
        projected_calls=probe.projected_calls,
        protected=probe.protected,
    ), intervention


def _environment(tmp_path, monkeypatch, *, axis=TomographyAxis.TOOL_EXECUTION_RESULT):
    import inverted.capability_ratchet.tomography_lab as module

    replay = ReplayStore(tmp_path / "replay")
    fixture = _fixture(replay)
    tomography = TomographyEvidenceStore(tmp_path / "tomography")
    study = _study(axis=axis)
    probe, intervention = _intervention(study, _probe(axis=axis))
    tomography.append_study(study)
    tomography.append_probe(probe)
    RecordingExecutor.instances.clear()
    monkeypatch.setattr(module, "ReplayExecutor", RecordingExecutor)
    lab = TomographyLab(replay, tomography)
    adapters = {"fake-model": FakeAdapter()}
    return lab, replay, tomography, fixture, study, probe, intervention, adapters


def _result(*, success=True):
    return SimpleNamespace(
        replay_result_id="replay-result-lab",
        semantic_pass=success,
        contract_pass=success,
        metrics={"score": 1.0 if success else 0.0},
        failure_classes=() if success else ("TOOL_EXECUTION_FAILURE",),
        child_failure_snapshot_id=None if success else "failure-child",
    )


def test_execute_passes_per_probe_provenance_through_canonical_replay_executor(tmp_path, monkeypatch):
    lab, replay, _tomography, _fixture_row, study, probe, intervention, adapters = _environment(tmp_path, monkeypatch)
    RecordingExecutor.result = _result(success=True)

    step = lab.execute(
        study,
        (probe,),
        {intervention.intervention_id: intervention},
        adapters,
        evidence_status_by_probe={probe.probe_id: "REUSED"},
        evidence_provenance_refs_by_probe={probe.probe_id: ("tool-result:canonical-1",)},
    )

    assert len(RecordingExecutor.instances) == 1
    executor = RecordingExecutor.instances[0]
    assert executor.store is replay
    assert executor.adapters is adapters
    assert len(executor.requests) == 1
    request = executor.requests[0]
    assert request.mode is ReplayMode.COUNTERFACTUAL
    assert request.metadata["tomography_evidence_status"] == "REUSED"
    assert request.metadata["tomography_evidence_provenance_refs"] == ("tool-result:canonical-1",)
    assert step.profile.certification_allowed is False
    assert step.model_calls_are_fake_only is True


def test_failed_probe_preserves_child_failure_and_never_certifies(tmp_path, monkeypatch):
    lab, _replay, tomography, _fixture_row, study, probe, intervention, adapters = _environment(
        tmp_path, monkeypatch, axis=TomographyAxis.TOOL_AVAILABILITY
    )
    RecordingExecutor.result = _result(success=False)

    step = lab.execute(study, (probe,), {intervention.intervention_id: intervention}, adapters)

    assert step.child_failure_snapshot_ids == ("failure-child",)
    assert step.outcomes[0].child_failure_snapshot_id == "failure-child"
    assert tomography.outcomes() == step.outcomes
    assert step.profile.certification_allowed is False


def test_protected_partition_is_rejected_before_executor_construction(tmp_path, monkeypatch):
    import inverted.capability_ratchet.tomography_lab as module

    replay = ReplayStore(tmp_path / "replay")
    _fixture(replay, partition=Partition.FRESH)
    tomography = TomographyEvidenceStore(tmp_path / "tomography")
    study = _study(axis=TomographyAxis.TOOL_AVAILABILITY, partition=Partition.FRESH)
    probe, intervention = _intervention(study, _probe(axis=TomographyAxis.TOOL_AVAILABILITY))
    RecordingExecutor.instances.clear()
    RecordingExecutor.result = _result(success=True)
    monkeypatch.setattr(module, "ReplayExecutor", RecordingExecutor)
    lab = TomographyLab(replay, tomography)

    with pytest.raises(ValueError, match="fresh/sealed tomography execution is forbidden"):
        lab.execute(study, (probe,), {intervention.intervention_id: intervention}, {"fake-model": FakeAdapter()})

    assert RecordingExecutor.instances == []
