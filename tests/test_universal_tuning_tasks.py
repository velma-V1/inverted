import json

from inverted.universal_tuning.tasks import (
    TASK_FAMILIES,
    build_qwen_task_pool,
    freeze_task_pool,
)


def test_pool_covers_all_families_with_120_unique_atomic_tasks_each():
    pool = build_qwen_task_pool(seed=20260907, per_family=120)
    assert len(TASK_FAMILIES) == 12
    assert len(pool.tasks) == 1440
    assert len({task.task_id for task in pool.tasks}) == 1440
    for family in TASK_FAMILIES:
        rows = [task for task in pool.tasks if task.family == family]
        assert len(rows) == 120
        assert {task.difficulty for task in rows} == {1, 2, 3, 4}
        assert all(task.prompt and task.expected is not None for task in rows)


def test_generation_is_deterministic_and_seed_sensitive():
    a = build_qwen_task_pool(seed=11, per_family=120)
    b = build_qwen_task_pool(seed=11, per_family=120)
    c = build_qwen_task_pool(seed=12, per_family=120)
    assert a.manifest_hash == b.manifest_hash
    assert [task.prompt for task in a.tasks] == [task.prompt for task in b.tasks]
    assert a.manifest_hash != c.manifest_hash


def test_freeze_writes_canonical_pool_and_hash(tmp_path):
    pool = build_qwen_task_pool(seed=5, per_family=120)
    manifest = freeze_task_pool(tmp_path, pool)
    pool_path = tmp_path / "task-pool-v2.json"
    manifest_path = tmp_path / "task-pool-v2-manifest.json"
    assert pool_path.exists() and manifest_path.exists()
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded["task_pool_sha256"] == pool.manifest_hash == manifest["task_pool_sha256"]
    assert loaded["task_count"] == 1440


def test_every_family_has_multiple_unique_prompts_per_difficulty():
    pool = build_qwen_task_pool(seed=77, per_family=120)
    for family in TASK_FAMILIES:
        for difficulty in (1, 2, 3, 4):
            prompts = {
                task.prompt for task in pool.tasks
                if task.family == family and task.difficulty == difficulty
            }
            assert len(prompts) >= 20


def test_manifest_changes_when_task_content_changes():
    from dataclasses import replace
    from inverted.universal_tuning.tasks import TaskPool
    pool = build_qwen_task_pool(seed=2, per_family=120)
    mutated = replace(pool.tasks[0], prompt=pool.tasks[0].prompt + " changed")
    other = TaskPool(seed=pool.seed, tasks=(mutated, *pool.tasks[1:]))
    assert other.manifest_hash != pool.manifest_hash


def test_every_generated_task_accepts_a_known_correct_answer():
    from inverted.universal_tuning.scoring import score_atomic_task
    pool = build_qwen_task_pool(seed=91, per_family=120)
    code_expr = {
        "max_default": lambda s: f"max(values, default={s['default']})",
        "all_gt": lambda s: f"all(x > {s['threshold']} for x in values)",
        "reverse_items": lambda s: "items[::-1]",
        "sum_multiples": lambda s: f"sum(x for x in values if x % {s['divisor']} == 0)",
        "first_default": lambda s: f"items[0] if items else {s['default']}",
        "sorted_unique": lambda s: "sorted(set(values))",
        "count_gt": lambda s: f"sum(1 for x in values if x > {s['threshold']})",
        "clamp_min": lambda s: f"max(value, {s['minimum']})",
        "any_equal": lambda s: f"any(x == {s['target']} for x in values)",
        "sum_values": lambda s: "sum(values)",
    }
    for task in pool.tasks:
        if task.scorer == "python_expr_batch":
            spec = task.expected[0]
            answer = [code_expr[spec["behavior"]](spec)]
        elif task.scorer == "contains_all_batch":
            answer = [" ".join(group) for group in task.expected]
        else:
            answer = task.expected
        score = score_atomic_task(task, json.dumps({"answer": answer}))
        assert score.semantic_pass, (task.task_id, task.scorer, task.expected, score)
        assert score.contract_pass, task.task_id
