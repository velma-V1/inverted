from __future__ import annotations

from types import SimpleNamespace

import pytest

from inverted.capability_ratchet.causal_core import InterventionDefinition, InterventionKind
from inverted.capability_ratchet.core import Partition, ReplayMode
from inverted.capability_ratchet.tomography_core import (
    TomographyAxis,
    TomographyProbe,
    TomographyStatus,
    TomographyStudy,
)
from inverted.capability_ratchet.tomography_lab import TomographyLab


SHA = "a" * 64
PATH = "request_envelopes.0.tool_result"


class ValidStore:
    def __init__(self):
        self.outcomes = []

    def validate(self, *args, **kwargs):
        return SimpleNamespace(ok=True)

    def append_outcome(self, outcome):
        self.outcomes.append(outcome)


class RecordingExecutor:
    instances = []
    result = None

    def __init__(self, *, store, adapters, snapshot_provider):
        self.store = store
        self.adapters = adapters
        self.snapshot_provider = snapshot_provider
        self.requests = []
        type(self).instances.append(self)

    def execute(self, request):
        self.requests.append(request)
        return type(self).result


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
        label="canonical supplied tool result",
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


def _lab(monkeypatch):
    import inverted.capability_ratchet.tomography_lab as module

    replay = ValidStore()
    causal = ValidStore()
    tomography = ValidStore()
    adapters = {"fake-model": object()}
    snapshot_provider = object()
    RecordingExecutor.instances.clear()
    monkeypatch.setattr(module, "ReplayExecutor", RecordingExecutor)
    lab = TomographyLab(
        test_replay=replay,
        causal=causal,
        tomography=tomography,
        snapshot_provider=snapshot_provider,
        adapters=adapters,
    )
    return lab, replay, causal, tomography, adapters, snapshot_provider


def _result(*, success=True):
    return SimpleNamespace(
        replay_result_id="replay-result-lab",
        failure_snapshot_id="failure-child" if not success else "failure-lab",
        semantic_success=success,
        contract_valid=success,
        score=1.0 if success else 0.0,
        first_divergence=None if success else "TOOL_EXECUTION_FAILURE",
        comparison_refs=("replay-baseline",),
    )


def test_execute_probe_passes_provenance_through_canonical_replay_executor(monkeypatch):
    lab, replay, _causal, _tomography, adapters, snapshot_provider = _lab(monkeypatch)
    study = _study()
    probe, intervention = _intervention(study, _probe())
    RecordingExecutor.result = _result(success=True)

    run = lab.execute_probe(
        study=study,
        probe=probe,
        intervention=intervention,
        root_failure_snapshot_id=study.failure_snapshot_id,
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        request_id="request-lab",
        evidence_status="REUSED",
        evidence_provenance_refs=("tool-result:canonical-1",),
    )

    assert len(RecordingExecutor.instances) == 1
    executor = RecordingExecutor.instances[0]
    assert executor.store is replay
    assert executor.adapters is adapters
    assert executor.snapshot_provider is snapshot_provider
    assert len(executor.requests) == 1
    request = executor.requests[0]
    assert request.mode is ReplayMode.COUNTERFACTUAL
    assert request.metadata["tomography_evidence_status"] == "REUSED"
    assert request.metadata["tomography_evidence_provenance_refs"] == ("tool-result:canonical-1",)
    assert run.profile is None


def test_failed_probe_preserves_child_failure_and_stage7_does_not_promote(monkeypatch):
    lab, _replay, _causal, tomography, _adapters, _snapshot_provider = _lab(monkeypatch)
    study = _study(axis=TomographyAxis.TOOL_AVAILABILITY)
    probe, intervention = _intervention(study, _probe(axis=TomographyAxis.TOOL_AVAILABILITY))
    RecordingExecutor.result = _result(success=False)

    run = lab.execute_probe(
        study=study,
        probe=probe,
        intervention=intervention,
        root_failure_snapshot_id=study.failure_snapshot_id,
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        request_id="request-failed",
    )

    assert run.outcome.child_failure_snapshot_id == "failure-child"
    assert tomography.outcomes == [run.outcome]
    assert run.profile is None


def test_protected_partition_is_rejected_before_executor_construction(monkeypatch):
    lab, _replay, _causal, _tomography, _adapters, _snapshot_provider = _lab(monkeypatch)
    study = _study(axis=TomographyAxis.TOOL_AVAILABILITY, partition=Partition.FRESH)
    probe, intervention = _intervention(study, _probe(axis=TomographyAxis.TOOL_AVAILABILITY))
    RecordingExecutor.result = _result(success=True)

    with pytest.raises(ValueError, match="fresh/sealed tomography execution is forbidden"):
        lab.execute_probe(
            study=study,
            probe=probe,
            intervention=intervention,
            root_failure_snapshot_id=study.failure_snapshot_id,
            source_model_id="fake-model",
            source_model_digest="fake-digest",
            request_id="request-protected",
        )

    assert RecordingExecutor.instances == []
