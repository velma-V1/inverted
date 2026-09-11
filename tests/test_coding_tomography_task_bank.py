from __future__ import annotations

import json
from pathlib import Path

from inverted.assistant_value.coding_tomography_runner import (
    manifest_diff,
    materialize_workspace,
    run_check,
    workspace_manifest,
)
from inverted.assistant_value.coding_tomography_tasks import build_builtin_task_bank


def _by_id(tasks):
    return {task["task_id"]: task for task in tasks}


def test_builtin_bank_materializes_external_oracles_and_git_repos(tmp_path: Path):
    tasks = build_builtin_task_bank(tmp_path / "bank")
    assert len(tasks) == 23
    for task in tasks:
        template = Path(task["workspace_template"])
        assert template.is_dir()
        assert (template / ".git").is_dir()
        oracle = Path(task["hidden_oracle_checks"][0]["argv"][1])
        assert oracle.is_file()
        assert template not in oracle.parents
        assert task["candidate_mechanisms"]


def test_false_green_and_packaging_cases_have_green_visible_but_red_hidden(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    for task_id in ("PU01-false-green", "PU25-packaging"):
        task = tasks[task_id]
        visible = run_check(task["visible_checks"][0], cwd=task["workspace_template"])
        hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])
        assert visible["ok"] is True
        assert hidden["ok"] is False


def test_deceptive_red_cases_start_red_and_hidden_oracle_rejects_initial_state(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    for task_id in (
        "PU08-generated-decoy",
        "PU09-stale-test",
        "PU10-wrong-fixture",
        "PU27-negative-space",
        "PU29-underengineering",
        "PU31-generalization",
        "PU37-misattribution",
        "PU39-evidence-composition",
    ):
        task = tasks[task_id]
        hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])
        assert hidden["ok"] is False, task_id


def test_workspace_manifest_and_diff_capture_created_modified_deleted(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.txt").write_text("one", encoding="utf-8")
    (root / "b.txt").write_text("delete", encoding="utf-8")
    before = workspace_manifest(root)

    (root / "a.txt").write_text("two", encoding="utf-8")
    (root / "b.txt").unlink()
    (root / "c.txt").write_text("new", encoding="utf-8")
    after = workspace_manifest(root)
    delta = manifest_diff(before, after)

    assert delta["modified"] == ["a.txt"]
    assert delta["deleted"] == ["b.txt"]
    assert delta["created"] == ["c.txt"]


def test_materialized_workspace_does_not_include_oracle_directory(tmp_path: Path):
    tasks = build_builtin_task_bank(tmp_path / "bank")
    task = tasks[0]
    workspace = materialize_workspace(task["workspace_template"], tmp_path / "work")
    assert workspace.is_dir()
    assert not (workspace / "oracles").exists()
    oracle = Path(task["hidden_oracle_checks"][0]["argv"][1])
    assert workspace not in oracle.parents


def test_executable_p10_compound_bank_is_present_and_sealed(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    p10_ids = {
        "PUC01-false-green-generated-package",
        "PUC02-shared-invariant-migration",
        "PUC03-circular-evidence-split-brain",
        "PUC04-correctly-unsolvable",
        "PUC05-active-path-generated-generalization",
    }

    assert p10_ids.issubset(tasks)
    for task_id in p10_ids:
        task = tasks[task_id]
        assert task["level"] == "P10"
        assert task["candidate_mechanisms"]
        oracle = Path(task["hidden_oracle_checks"][0]["argv"][1])
        template = Path(task["workspace_template"])
        assert oracle.is_file()
        assert template not in oracle.parents


def test_p10_mutation_cases_start_hidden_red(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    for task_id in (
        "PUC01-false-green-generated-package",
        "PUC02-shared-invariant-migration",
        "PUC03-circular-evidence-split-brain",
        "PUC05-active-path-generated-generalization",
    ):
        task = tasks[task_id]
        hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])
        assert hidden["ok"] is False, task_id


def test_p10_correctly_unsolvable_case_requires_no_edit_plus_clarification(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    task = tasks["PUC04-correctly-unsolvable"]

    hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])

    assert hidden["ok"] is True
    assert task["response_oracle"]["must_not_modify_files"] is True
    assert "deployment" in task["response_oracle"]["must_contain_any"]


def test_specialized_system_behavior_frontier_cases_are_present(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    expected = {
        "PUC06-parallel-opportunity",
        "PUC07-parallel-hazard",
        "PUC08-transient-retry",
        "PUC09-false-tool-success",
        "PUC10-unfinished-work",
    }
    assert expected.issubset(tasks)
    for task_id in expected:
        assert tasks[task_id]["candidate_mechanisms"]
        assert tasks[task_id]["level"] in {"P8","P9","P10"}


def test_false_tool_success_and_unfinished_work_are_visible_green_hidden_red(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    for task_id in ("PUC09-false-tool-success", "PUC10-unfinished-work"):
        task = tasks[task_id]
        visible = run_check(task["visible_checks"][0], cwd=task["workspace_template"])
        hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])
        assert visible["ok"] is True, task_id
        assert hidden["ok"] is False, task_id


def test_parallelism_cases_start_hidden_red(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    for task_id in ("PUC06-parallel-opportunity", "PUC07-parallel-hazard"):
        task = tasks[task_id]
        hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])
        assert hidden["ok"] is False, task_id


def test_task_ids_are_unique_and_bank_has_23_executable_cases(tmp_path: Path):
    tasks = build_builtin_task_bank(tmp_path / "bank")
    ids = [task["task_id"] for task in tasks]
    assert len(ids) == 23
    assert len(set(ids)) == 23


def test_final_system_level_cases_have_correct_scientific_boundaries(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))

    least = tasks["PUC11-least-privilege-tool-choice"]
    context = tasks["PUC12-context-pressure-authority"]
    mcp = tasks["PUC13-mcp-reference-escalation"]

    assert {"M05","M25","M26","M39"}.issubset(least["candidate_mechanisms"])
    assert {"M17","M18","M19","M20","M37"}.issubset(context["candidate_mechanisms"])
    assert {"M05","M27","M28","M29"}.issubset(mcp["candidate_mechanisms"])
    assert mcp["replay_eligible"] is False
    assert least["replay_eligible"] is True
    assert context["replay_eligible"] is True

    assert isinstance(context.get("resume_spec"), dict)
    assert context["resume_spec"]["candidate_mechanisms"]
    assert "resume-hidden" in {
        row["id"] for row in context["resume_spec"]["hidden_oracle_checks"]
    }

    for task_id in (
        "PUC11-least-privilege-tool-choice",
        "PUC12-context-pressure-authority",
        "PUC13-mcp-reference-escalation",
    ):
        task = tasks[task_id]
        visible = run_check(task["visible_checks"][0], cwd=task["workspace_template"])
        hidden = run_check(task["hidden_oracle_checks"][0], cwd=task["workspace_template"])
        assert visible["ok"] is True, task_id
        assert hidden["ok"] is False, task_id


def test_mcp_answer_is_not_present_in_model_visible_puc13_workspace(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    task = tasks["PUC13-mcp-reference-escalation"]
    template = Path(task["workspace_template"])

    visible_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in template.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    assert "mcp-current-2026" not in visible_text
    oracle = Path(task["hidden_oracle_checks"][0]["argv"][1])
    assert "mcp-current-2026" in oracle.read_text(encoding="utf-8")


def test_puc11_privileged_decoy_starts_without_outside_side_effect(tmp_path: Path):
    tasks = _by_id(build_builtin_task_bank(tmp_path / "bank"))
    task = tasks["PUC11-least-privilege-tool-choice"]
    template = Path(task["workspace_template"])
    assert not (template.parent / "global_state.json").exists()
    assert (template / "admin_update.py").is_file()
    assert (template / "safe_update.py").is_file()
