import json
from pathlib import Path

import pytest

from inverted_brain.contracts import DifficultyVector
from inverted_brain.taskgen import GRAMMARS, generate_task
from inverted_brain.task_manifest import freeze_task, verify_task, prompt_fingerprint


EXPECTED_GRAMMARS = {
    "dependency_repair", "stale_state", "constraint_interaction",
    "evidence_selection", "reconciliation", "interface_novelty",
}


def tree_bytes(root: Path):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_six_preregistered_grammars_exist():
    assert set(GRAMMARS) == EXPECTED_GRAMMARS


def test_generation_is_deterministic_and_verifier_is_hidden(tmp_path):
    difficulty = DifficultyVector(constraints=3, dependency_depth=2, distractors=2)
    a = tmp_path / "a"
    b = tmp_path / "b"
    spec_a = generate_task("dependency_repair", difficulty, 1234, a)
    spec_b = generate_task("dependency_repair", difficulty, 1234, b)
    assert tree_bytes(a) == tree_bytes(b)
    assert spec_a.task_id == spec_b.task_id
    assert (a / "workspace").is_dir()
    assert (a / "verify" / "verify.py").is_file()
    assert not (a / "workspace" / "verify").exists()
    visible = (a / "task.json").read_text() + "\n" + "\n".join(
        p.read_text(errors="ignore") for p in (a / "workspace").rglob("*") if p.is_file()
    )
    hidden = json.loads((a / "verify" / "gold.json").read_text())
    assert hidden["answer_token"] not in visible


def test_different_seed_or_difficulty_changes_task(tmp_path):
    base = DifficultyVector(constraints=2, dependency_depth=1)
    deeper = DifficultyVector(constraints=2, dependency_depth=4)
    generate_task("dependency_repair", base, 10, tmp_path / "a")
    generate_task("dependency_repair", base, 11, tmp_path / "b")
    generate_task("dependency_repair", deeper, 10, tmp_path / "c")
    assert tree_bytes(tmp_path / "a") != tree_bytes(tmp_path / "b")
    assert tree_bytes(tmp_path / "a") != tree_bytes(tmp_path / "c")


def test_manifest_detects_mutation_and_prompt_fingerprint_blocks_overlap(tmp_path):
    task = tmp_path / "task"
    generate_task("stale_state", DifficultyVector(stale_evidence_risk=3), 99, task)
    manifest = freeze_task(task)
    assert manifest
    assert verify_task(task) == []
    (task / "workspace" / "source.json").write_text("{}\n", encoding="utf-8")
    assert "workspace/source.json" in verify_task(task)

    prompt = json.loads((task / "task.json").read_text())["prompt"]
    fingerprint = prompt_fingerprint(prompt)
    with pytest.raises(ValueError, match="contamination"):
        generate_task(
            "stale_state", DifficultyVector(stale_evidence_risk=3), 99,
            tmp_path / "dup", forbidden_prompt_hashes={fingerprint},
        )


@pytest.mark.parametrize("grammar", sorted(EXPECTED_GRAMMARS))
def test_every_grammar_builds_a_self_verifying_task(grammar, tmp_path):
    task = tmp_path / grammar
    spec = generate_task(grammar, DifficultyVector(constraints=2, distractors=1), 777, task)
    assert spec.grammar == grammar
    task_json = json.loads((task / "task.json").read_text())
    assert task_json["grammar"] == grammar
    assert task_json["constraints"]
    assert (task / "verify" / "verify.py").read_text().strip()
