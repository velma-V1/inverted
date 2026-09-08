from __future__ import annotations

from inverted.capability_ratchet import FailureFixture, Partition
from inverted.capability_ratchet.autopsy import FailureAutopsy
from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    InterventionKind,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.interventions import TailoredInterventionGenerator
from inverted.capability_ratchet.replay_store import ReplayStore


def _case(
    tmp_path,
    *,
    failure_classes=("SEMANTIC_FAIL",),
    semantic=False,
    contract=True,
    completed=True,
    family="ARITHMETIC",
):
    replay = ReplayStore(tmp_path / "replay")
    visible_payload = {
        "request_envelopes": [{
            "model": "model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "temperature": 0.7, "num_predict": 128},
            "messages": [{"role": "user", "content": "Solve 17 + 25 and return the required answer object."}],
        }]
    }
    visible = replay.put_asset(visible_payload)
    forensic = replay.put_asset({
        "focus_observation": {
            "observation_id": "obs-intervention",
            "task_id": "task-intervention",
            "family": family,
            "semantic_pass": semantic,
            "contract_pass": contract,
            "completed": completed,
            "failure_classes": list(failure_classes),
        },
        "raw_trial": {
            "trial_id": "trial-intervention",
            "raw_calls": [{
                "request": visible_payload["request_envelopes"][0],
                "response": {
                    "done": completed,
                    "done_reason": "stop" if completed else "length",
                },
            }],
        },
        "oracle_material": {"expected": 42},
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-intervention",
        source_campaign_id="campaign",
        source_trial_id="trial-intervention",
        focus_observation_id="obs-intervention",
        focus_task_id="task-intervention",
        batch_task_ids=("task-intervention",),
        family=family,
        failure_classes=tuple(failure_classes),
        source_model_id="model",
        source_model_digest="digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0.7, "thinking_budget": 0},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash="2" * 64,
        oracle_ref="hidden-oracle-reference",
        expected_contract="answer object",
        source_evidence_refs=("raw:intervention",),
        forensic_asset_sha256=forensic,
    )
    replay.append(fixture)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    report = FailureAutopsy(replay, causal).analyze(fixture)
    return fixture, replay, causal, report


def _rendered_overrides(interventions) -> str:
    return repr([dict(item.overrides) for item in interventions]).lower()


def test_arithmetic_failure_generates_competing_system_model_and_sham_treatments(tmp_path) -> None:
    fixture, replay, causal, report = _case(tmp_path)
    generated = TailoredInterventionGenerator(replay, causal).generate(fixture, report)

    assert generated
    owners = {hypothesis.owner_candidate for hypothesis in report.hypotheses}
    assert ArchitectureOwner.SYSTEM in owners and ArchitectureOwner.MODEL in owners
    assert any(item.kind is InterventionKind.DETERMINISTIC for item in generated)
    assert any(item.kind is InterventionKind.COGNITION for item in generated)
    target_ids = {item.intervention_id for item in generated if item.kind is not InterventionKind.SHAM}
    shams = [item for item in generated if item.kind is InterventionKind.SHAM]
    assert shams
    assert all(item.sham_for in target_ids for item in shams)


def test_deterministic_substitute_projects_zero_model_calls(tmp_path) -> None:
    fixture, replay, causal, report = _case(tmp_path)
    generated = TailoredInterventionGenerator(replay, causal).generate(fixture, report)
    deterministic = [item for item in generated if item.kind is InterventionKind.DETERMINISTIC]
    assert deterministic
    assert all(item.projected_physical_calls == 0 for item in deterministic)
    assert all(item.changed_dimensions == () and dict(item.overrides) == {} for item in deterministic)


def test_contract_failure_generates_contract_treatment_with_registered_prompt_dimension(tmp_path) -> None:
    fixture, replay, causal, report = _case(
        tmp_path,
        failure_classes=("CONTRACT_FAIL",),
        semantic=True,
        contract=False,
    )
    generated = TailoredInterventionGenerator(replay, causal).generate(fixture, report)
    prompt = [item for item in generated if item.kind is InterventionKind.PROMPT]
    assert prompt
    assert all(item.changed_dimensions for item in prompt)
    assert all(set(item.changed_dimensions) == set(item.overrides) for item in prompt)
    assert all(path.startswith("request_envelopes.") for item in prompt for path in item.changed_dimensions)


def test_reasoning_cap_generates_bounded_cognition_not_unbounded_retry(tmp_path) -> None:
    fixture, replay, causal, report = _case(
        tmp_path,
        failure_classes=("REASONING_CAP_EXHAUSTION", "COMPLETION_FAIL"),
        semantic=False,
        contract=False,
        completed=False,
    )
    generated = TailoredInterventionGenerator(replay, causal).generate(fixture, report)
    cognition = [item for item in generated if item.kind is InterventionKind.COGNITION]
    assert cognition
    assert any(
        path.endswith("options.num_predict")
        for item in cognition
        for path in item.changed_dimensions
    )
    assert all("retry" not in item.label.lower() for item in generated)


def test_unknown_failure_preserves_protected_exploration(tmp_path) -> None:
    fixture, replay, causal, report = _case(
        tmp_path,
        failure_classes=("NOVEL_UNCLASSIFIED",),
        family="NOVEL",
    )
    generated = TailoredInterventionGenerator(replay, causal).generate(fixture, report)
    assert any(item.protected_exploration for item in generated)


def test_intervention_generation_cannot_leak_oracle_material(tmp_path) -> None:
    fixture, replay, causal, report = _case(tmp_path)
    generated = TailoredInterventionGenerator(replay, causal).generate(fixture, report)
    rendered = _rendered_overrides(generated)
    assert "hidden-oracle-reference" not in rendered
    assert "oracle_material" not in rendered
    assert "expected': 42" not in rendered


def test_generation_is_deterministic_idempotent_and_registered(tmp_path) -> None:
    fixture, replay, causal, report = _case(tmp_path)
    generator = TailoredInterventionGenerator(replay, causal)
    first = generator.generate(fixture, report)
    before = causal.intervention_registry_path.read_bytes()
    second = generator.generate(fixture, report)
    assert [item.intervention_id for item in first] == [item.intervention_id for item in second]
    assert causal.intervention_registry_path.read_bytes() == before
    assert all(causal.get_intervention(item.intervention_id) == item for item in first)
    assert causal.validate().ok
