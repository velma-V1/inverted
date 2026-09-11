from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.assistant_value.coding_tomography_campaign import (
    _mechanism_results,
    build_campaign_plan,
    run_coding_tomography_campaign,
)
from inverted.assistant_value.coding_tomography_interventions import (
    apply_intervention,
    selected_interventions,
)
from inverted.assistant_value.coding_tomography_tasks import build_builtin_task_bank


def _config(max_sessions: int = 162):
    return {
        "coding_tomography":{
            "max_sessions":max_sessions,
            "native_repeats":2,
            "intervention_repeats":2,
            "include_common_interventions":True,
            "observability_repeats":1,
            "observability_subjects":["claude_code"],
            "observability_task_ids":[
                "PUC01-false-green-generated-package",
                "PUC05-active-path-generated-generalization",
            ],
            "timeout_s":30,
            "task_ids":[
                "PU01-false-green",
                "PU09-stale-test",
                "PU29-underengineering",
                "PU31-generalization",
                "PU37-misattribution",
                "PUC01-false-green-generated-package",
                "PUC02-shared-invariant-migration",
                "PUC03-circular-evidence-split-brain",
                "PUC04-correctly-unsolvable",
                "PUC05-active-path-generated-generalization",
            ],
            "subjects":[
                {"name":"claude_code","executable":"definitely-missing-claude","extra_args":[]},
                {"name":"codex","executable":"definitely-missing-codex","extra_args":[]},
            ],
        }
    }


def test_campaign_plan_is_bounded_and_matched(tmp_path: Path):
    tasks = build_builtin_task_bank(tmp_path / "bank")
    plan = build_campaign_plan(_config(), tasks)

    assert plan["task_count"] == 10
    assert plan["planned_sessions"] == 162
    assert len(plan["subjects"]) == 2

    native = [row for row in plan["entries"] if row["kind"] == "NATIVE_OBSERVATION"]
    causal = [row for row in plan["entries"] if row["kind"] == "CAUSAL_INTERVENTION"]
    assert len(native) == 40
    assert len(causal) == 120
    observed = [row for row in plan["entries"] if row["kind"] == "OBSERVABILITY_AUGMENTED"]
    assert len(observed) == 2
    assert {row["subject"]["name"] for row in observed} == {"claude_code"}

    by_subject_task = {}
    for row in native:
        by_subject_task.setdefault((row["subject"]["name"],row["task_id"]),0)
        by_subject_task[(row["subject"]["name"],row["task_id"])] += 1
    assert set(by_subject_task.values()) == {2}


def test_campaign_refuses_session_budget_overrun_before_subject_run(tmp_path: Path):
    tasks = build_builtin_task_bank(tmp_path / "bank")
    with pytest.raises(ValueError, match="exceed max_sessions"):
        build_campaign_plan(_config(max_sessions=161), tasks)


def test_dry_run_never_requires_installed_subjects(tmp_path: Path):
    result = run_coding_tomography_campaign(
        _config(),
        output_dir=tmp_path / "runs",
        run_id="dry",
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["planned_sessions"] == 162
    root = Path(result["run_root"])
    assert (root / "campaign-plan.json").is_file()
    assert (root / "mechanism-registry.json").is_file()
    assert (root / "pathology-registry.json").is_file()
    versions = json.loads((root / "subject-versions.json").read_text(encoding="utf-8"))
    assert all(row["available"] is False for row in versions)


def test_project_instruction_intervention_is_subject_native(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    intervention = next(
        row for row in selected_interventions("PU01-false-green")
        if row["id"] == "I-PROJECT-INSTRUCTION-VERIFY"
    )

    claude_root = root / "claude"
    codex_root = root / "codex"
    claude_root.mkdir()
    codex_root.mkdir()

    apply_intervention(claude_root, intervention, subject="claude_code")
    apply_intervention(codex_root, intervention, subject="codex")

    assert (claude_root / "CLAUDE.md").is_file()
    assert not (claude_root / "AGENTS.md").exists()
    assert (codex_root / "AGENTS.md").is_file()
    assert not (codex_root / "CLAUDE.md").exists()


def test_task_specific_intervention_changes_only_declared_factor(tmp_path: Path):
    tasks = {row["task_id"]:row for row in build_builtin_task_bank(tmp_path / "bank")}
    task = tasks["PU09-stale-test"]
    work = tmp_path / "work"
    import shutil
    shutil.copytree(task["workspace_template"],work)

    before = (work / "visible_check.py").read_text(encoding="utf-8")
    intervention = next(
        row for row in selected_interventions(task["task_id"],include_common=False)
        if row["id"] == "I09-correct-visible-test"
    )
    result = apply_intervention(work,intervention,subject="codex")
    after = (work / "visible_check.py").read_text(encoding="utf-8")

    assert "== 80" in before
    assert "== 90" in after
    assert result["changed_paths"] == ["visible_check.py"]


def test_multi_mechanism_factor_does_not_promote_each_mechanism_to_causal():
    tasks = [
        {"task_id":"t1","family":"f1","candidate_mechanisms":["M01","M02"]},
        {"task_id":"t2","family":"f2","candidate_mechanisms":["M01","M02"]},
    ]
    summaries = [
        {"task_id":"t1","kind":"NATIVE_OBSERVATION","oracle_success":False},
        {"task_id":"t2","kind":"NATIVE_OBSERVATION","oracle_success":False},
    ]
    paired = {
        "results":{
            "s|t1|i":{
                "subject":"s",
                "task_id":"t1",
                "intervention_id":"i",
                "mechanisms":["M01","M02"],
                "success_delta":1.0,
                "elapsed_s_delta":0.0,
                "event_count_delta":0.0,
                "verification_after_last_edit_baseline":0.0,
                "verification_after_last_edit_treatment":1.0,
            }
        }
    }

    result = _mechanism_results(tasks, summaries, paired)
    m01 = result["mechanisms"]["M01"]
    m02 = result["mechanisms"]["M02"]

    assert m01["bundle_intervention_count"] == 1
    assert m01["identifiable_intervention_count"] == 0
    assert m01["status"] == "REPLICATED"
    assert m02["status"] == "REPLICATED"
    assert m01["implementation_decision"] == "UNKNOWN"
    assert m02["implementation_decision"] == "UNKNOWN"
