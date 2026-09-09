from __future__ import annotations

import json

from inverted.capability_ratchet.cli import main
from inverted.capability_ratchet.core import FailureFixture, Partition
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.tomography_core import (
    TomographyAssessment,
    TomographyDisposition,
)
from inverted.capability_ratchet.tomography_store import TomographyEvidenceStore


SHA = "a" * 64


def _roots(tmp_path):
    replay_root = tmp_path / "replay"
    causal_root = tmp_path / "causal"
    tomography_root = tmp_path / "tomography"
    replay = ReplayStore(replay_root)
    visible = {
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "num_predict": 64, "temperature": 0.0},
            "tools": [
                {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}},
                {"type": "function", "function": {"name": "other", "parameters": {"type": "object"}}},
            ],
            "messages": [{"role": "user", "content": "Use the correct visible tool."}],
        }],
        "task": {"kind": "stage7-cli"},
    }
    fixture = FailureFixture(
        failure_snapshot_id="failure-cli",
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
        partition=Partition.HISTORICAL,
        model_visible_asset_sha256=replay.put_asset(visible),
        state_hash=SHA,
        oracle_ref="oracle:stage7-cli",
        expected_contract="return a valid answer",
        source_evidence_refs=("evidence:stage7-cli",),
        oracle_asset_sha256=replay.put_asset({"answer": "lookup"}),
        metadata={
            "stage7_evidence": {
                "divergence_class": "TOOL_SELECTION",
                "tool_available": True,
                "tool_selected": False,
                "required_tool_name": "lookup",
            }
        },
    )
    replay.append(fixture)
    return replay_root, causal_root, tomography_root


def _argv(command, replay_root, causal_root, tomography_root, *extra):
    return [
        command,
        "--replay-root", str(replay_root),
        "--causal-root", str(causal_root),
        "--tomography-root", str(tomography_root),
        *extra,
    ]


def _stdout_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_scan_tomography_eligibility_is_zero_call_and_finds_stage7_fixture(tmp_path, capsys):
    replay_root, causal_root, tomography_root = _roots(tmp_path)
    rc = main(_argv("scan-tomography-eligibility", replay_root, causal_root, tomography_root))
    payload = _stdout_json(capsys)
    assert rc == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["status"] == "TOMOGRAPHY_ELIGIBILITY_SCAN"
    assert payload["rows"] == [{
        "failure_snapshot_id": "failure-cli",
        "divergence": "TOOL_SELECTION",
        "eligibility": "ELIGIBLE",
        "decision_ids": ["D2", "D6"],
        "reason": "failure has a reconstructable Stage-7 ownership question",
    }]


def test_auto_plan_persists_zero_call_study_then_named_plan_and_show_work(tmp_path, capsys):
    replay_root, causal_root, tomography_root = _roots(tmp_path)
    rc = main(_argv(
        "plan-tomography", replay_root, causal_root, tomography_root, "--auto-eligible"
    ))
    payload = _stdout_json(capsys)
    assert rc == 0
    assert payload["MODEL_CALLS"] == 0
    assert payload["status"] == "TOMOGRAPHY_PLAN_READY"
    assert len(payload["plans"]) == 1
    plan = payload["plans"][0]
    assert plan["study"]["failure_snapshot_id"] == "failure-cli"
    assert plan["study"]["status"] == "PLANNED"
    assert [row["axis"] for row in plan["probes"]] == ["TOOL_SELECTION"]
    study_id = plan["study"]["study_id"]

    rc = main(_argv(
        "plan-tomography", replay_root, causal_root, tomography_root, "--study-id", study_id
    ))
    named = _stdout_json(capsys)
    assert rc == 0 and named["MODEL_CALLS"] == 0
    assert named["study"]["study_id"] == study_id
    assert [row["axis"] for row in named["probes"]] == ["TOOL_SELECTION"]

    rc = main(_argv(
        "show-tomography-study", replay_root, causal_root, tomography_root, "--study-id", study_id
    ))
    shown = _stdout_json(capsys)
    assert rc == 0 and shown["MODEL_CALLS"] == 0
    assert shown["study"]["study_id"] == study_id
    assert shown["tomography_store_valid"] is True


def test_show_tomography_assessment_is_zero_call(tmp_path, capsys):
    replay_root, causal_root, tomography_root = _roots(tmp_path)
    main(_argv("plan-tomography", replay_root, causal_root, tomography_root, "--auto-eligible"))
    planned = _stdout_json(capsys)
    study_id = planned["plans"][0]["study"]["study_id"]
    tomography = TomographyEvidenceStore(tomography_root)
    tomography.append_assessment(TomographyAssessment(
        profile_id="profile-cli",
        study_id=study_id,
        dispositions=(TomographyDisposition.TOOL_SELECTION_DEFICIT,),
        supported_hypotheses=("hyp-cli",),
        falsified_hypotheses=(),
        evidence_refs=("replay-evidence-cli",),
        next_decisions=("D6",),
        route_back_stage=None,
        model_internal_boundary=False,
        promotion_allowed=False,
        certification_allowed=False,
    ))

    rc = main(_argv(
        "show-tomography-assessment", replay_root, causal_root, tomography_root, "--study-id", study_id
    ))
    payload = _stdout_json(capsys)
    assert rc == 0 and payload["MODEL_CALLS"] == 0
    assert payload["assessment"]["profile_id"] == "profile-cli"
    assert payload["assessment"]["dispositions"] == ["TOOL_SELECTION_DEFICIT"]


def test_tomography_cli_never_exposes_execution_authorization(tmp_path, capsys):
    replay_root, causal_root, tomography_root = _roots(tmp_path)
    rc = main(_argv("scan-tomography-eligibility", replay_root, causal_root, tomography_root))
    payload = _stdout_json(capsys)
    assert rc == 0 and payload["MODEL_CALLS"] == 0
    rendered = json.dumps(payload).lower()
    assert "allow-model-calls" not in rendered
    assert "execute-tomography" not in rendered
