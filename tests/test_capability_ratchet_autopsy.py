from __future__ import annotations

from inverted.capability_ratchet import FailureFixture, Partition
from inverted.capability_ratchet.autopsy import FailureAutopsy
from inverted.capability_ratchet.causal_core import ArchitectureOwner, DivergenceClass
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.replay_store import ReplayStore


def _case(tmp_path, *, failure_classes, semantic=False, contract=True, completed=True, family="ARITHMETIC", metadata=None):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({
        "request_envelopes": [{
            "model": "model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "temperature": 0.7, "num_predict": 128},
            "messages": [{"role": "user", "content": "Solve the task without hidden oracle data."}],
        }]
    })
    focus = {
        "observation_id": "obs-autopsy",
        "task_id": "task-autopsy",
        "family": family,
        "semantic_pass": semantic,
        "contract_pass": contract,
        "completed": completed,
        "failure_classes": list(failure_classes),
        "metadata": [] if metadata is None else list(metadata),
    }
    forensic = replay.put_asset({
        "focus_observation": focus,
        "raw_trial": {
            "trial_id": "trial-autopsy",
            "raw_calls": [{
                "request": {"think": False},
                "response": {"done": completed, "done_reason": "stop" if completed else "length"},
            }],
        },
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-autopsy",
        source_campaign_id="campaign",
        source_trial_id="trial-autopsy",
        focus_observation_id="obs-autopsy",
        focus_task_id="task-autopsy",
        batch_task_ids=("task-autopsy",),
        family=family,
        failure_classes=tuple(failure_classes),
        source_model_id="model",
        source_model_digest="digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0.7, "thinking_budget": 0},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash="1" * 64,
        oracle_ref="hidden-oracle-reference",
        expected_contract="answer object",
        source_evidence_refs=("raw:autopsy",),
        forensic_asset_sha256=forensic,
        metadata={} if metadata is None else dict(metadata),
    )
    replay.append(fixture)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    return fixture, replay, causal


def test_contract_failure_localizes_before_semantic_cognition(tmp_path) -> None:
    fixture, replay, causal = _case(
        tmp_path,
        failure_classes=("CONTRACT_FAIL",),
        semantic=True,
        contract=False,
        completed=True,
    )
    report = FailureAutopsy(replay, causal).analyze(fixture)
    assert report.first_divergence.divergence_class is DivergenceClass.CONTRACT_INTERFACE
    assert report.first_divergence.observable_path.endswith("contract_pass")
    assert ArchitectureOwner.SYSTEM in {item.owner_candidate for item in report.hypotheses}
    assert all(
        "oracle" not in ref.lower()
        for hypothesis in report.hypotheses
        for ref in hypothesis.divergence.evidence_refs
    )


def test_reasoning_cap_failure_points_to_observed_completion_boundary(tmp_path) -> None:
    fixture, replay, causal = _case(
        tmp_path,
        failure_classes=("REASONING_CAP_EXHAUSTION", "COMPLETION_FAIL"),
        semantic=False,
        contract=False,
        completed=False,
    )
    report = FailureAutopsy(replay, causal).analyze(fixture)
    assert report.first_divergence.divergence_class is DivergenceClass.INSUFFICIENT_REASONING
    assert "done_reason" in report.first_divergence.observable_path
    assert any(item.owner_candidate is ArchitectureOwner.MODEL for item in report.hypotheses)


def test_semantic_arithmetic_failure_keeps_competing_system_and_model_hypotheses(tmp_path) -> None:
    fixture, replay, causal = _case(
        tmp_path,
        failure_classes=("SEMANTIC_FAIL",),
        semantic=False,
        contract=True,
        completed=True,
        family="ARITHMETIC",
    )
    report = FailureAutopsy(replay, causal).analyze(fixture)
    owners = {item.owner_candidate for item in report.hypotheses}
    assert ArchitectureOwner.SYSTEM in owners
    assert ArchitectureOwner.MODEL in owners
    assert len(report.hypotheses) <= 4


def test_authority_scope_failure_is_not_misdiagnosed_as_reasoning(tmp_path) -> None:
    fixture, replay, causal = _case(
        tmp_path,
        failure_classes=("AUTHORITY_SCOPE",),
        metadata=(("authority_scope_error", True),),
    )
    report = FailureAutopsy(replay, causal).analyze(fixture)
    assert report.first_divergence.divergence_class is DivergenceClass.AUTHORITY_SCOPE
    assert any(item.owner_candidate is ArchitectureOwner.SYSTEM for item in report.hypotheses)


def test_unknown_failure_stays_unknown_and_protected(tmp_path) -> None:
    fixture, replay, causal = _case(
        tmp_path,
        failure_classes=("NOVEL_UNCLASSIFIED",),
        family="NOVEL",
    )
    report = FailureAutopsy(replay, causal).analyze(fixture)
    assert report.first_divergence.divergence_class is DivergenceClass.UNKNOWN_NOVEL
    assert report.unresolved_questions
    assert any(item.protected_exploration for item in report.hypotheses)


def test_reautopsy_is_deterministic_and_idempotent(tmp_path) -> None:
    fixture, replay, causal = _case(
        tmp_path,
        failure_classes=("CONTRACT_FAIL",),
        semantic=True,
        contract=False,
    )
    autopsy = FailureAutopsy(replay, causal)
    first = autopsy.analyze(fixture)
    before = causal.hypothesis_path.read_bytes()
    second = autopsy.analyze(fixture)
    assert [item.hypothesis_id for item in first.hypotheses] == [item.hypothesis_id for item in second.hypotheses]
    assert causal.hypothesis_path.read_bytes() == before
