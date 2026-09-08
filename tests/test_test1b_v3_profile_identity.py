from __future__ import annotations

from dataclasses import fields, replace

import inverted.universal_tuning as tuning
from inverted.universal_tuning import campaign
from inverted.universal_tuning.core import AtomicTask, Profile
from inverted.universal_tuning.scheduler import AdaptiveScheduler, ModelMetadata
from inverted.universal_tuning.tasks import TaskPool


FAMILY = "LOGIC_CONSTRAINTS"


def _api():
    assert hasattr(tuning, "profile_fingerprint")
    return tuning.profile_fingerprint


def _profile() -> Profile:
    return Profile(
        thinking_budget=1024,
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        min_p=0.05,
        presence_penalty=0.25,
        repeat_penalty=1.1,
        typical_p=0.95,
        repeat_last_n=128,
        frequency_penalty=0.5,
        num_keep=32,
        num_ctx=8192,
        num_batch=256,
        num_gpu=20,
        main_gpu=0,
        use_mmap=True,
        num_thread=8,
        draft_num_predict=64,
        final_max_tokens=768,
        stop=("STOP",),
        truncate=False,
        shift=True,
        logprobs=False,
        top_logprobs=3,
    )


_ALTERNATES = {
    "thinking_budget": 2048,
    "temperature": 0.8,
    "top_p": 0.8,
    "top_k": 80,
    "min_p": 0.1,
    "presence_penalty": 0.5,
    "repeat_penalty": 1.2,
    "typical_p": 0.9,
    "repeat_last_n": 256,
    "frequency_penalty": 0.75,
    "num_keep": 64,
    "num_ctx": 16384,
    "num_batch": 512,
    "num_gpu": 30,
    "main_gpu": 1,
    "use_mmap": False,
    "num_thread": 12,
    "draft_num_predict": 128,
    "final_max_tokens": 1024,
    "stop": ("END",),
    "truncate": True,
    "shift": False,
    "logprobs": True,
    "top_logprobs": 5,
}


def test_profile_fingerprint_is_deterministic_and_covers_every_field() -> None:
    fingerprint = _api()
    base = _profile()
    baseline = fingerprint(base)

    assert len(baseline) == 64
    assert baseline == fingerprint(replace(base))
    assert set(_ALTERNATES) == {field.name for field in fields(Profile)}

    changed = {
        field_name: fingerprint(replace(base, **{field_name: alternate}))
        for field_name, alternate in _ALTERNATES.items()
    }
    assert all(value != baseline for value in changed.values())
    assert len(set(changed.values())) == len(changed)


def test_profile_fingerprint_rejects_non_profile() -> None:
    fingerprint = _api()
    try:
        fingerprint({"temperature": 0.7})
    except TypeError as exc:
        assert "Profile" in str(exc)
    else:
        raise AssertionError("non-Profile value must be rejected")


def _pool() -> TaskPool:
    tasks = tuple(
        AtomicTask(
            task_id=f"logic-{index:03d}",
            family=FAMILY,
            difficulty=1,
            prompt="Return B.",
            expected="B",
            scorer="exact_value",
        )
        for index in range(120)
    )
    return TaskPool(seed=20260908, tasks=tasks)


def test_scheduler_trial_ids_include_full_profile_identity() -> None:
    fingerprint = _api()
    pool = _pool()
    scheduler = AdaptiveScheduler(pool, ModelMetadata())
    baseline = Profile(0, 0.7, top_p=0.9)
    candidate_a = Profile(0, 0.7, top_p=0.8)
    candidate_b = Profile(0, 0.7, top_p=0.6)

    trials_a = scheduler.paired_trials(
        family=FAMILY,
        stage="gate",
        baseline=baseline,
        candidate=candidate_a,
        atomic_count=5,
        task_offset=0,
        decision_reason="PROFILE_IDENTITY_A",
    )
    trials_b = scheduler.paired_trials(
        family=FAMILY,
        stage="gate",
        baseline=baseline,
        candidate=candidate_b,
        atomic_count=5,
        task_offset=0,
        decision_reason="PROFILE_IDENTITY_B",
    )

    baseline_a = next(item for item in trials_a if item.profile == baseline)
    baseline_b = next(item for item in trials_b if item.profile == baseline)
    variant_a = next(item for item in trials_a if item.profile == candidate_a)
    variant_b = next(item for item in trials_b if item.profile == candidate_b)

    assert baseline_a.trial_id == baseline_b.trial_id
    assert variant_a.trial_id != variant_b.trial_id
    assert fingerprint(candidate_a)[:16] in variant_a.trial_id
    assert fingerprint(candidate_b)[:16] in variant_b.trial_id


def test_campaign_profile_key_is_the_canonical_full_profile_fingerprint() -> None:
    fingerprint = _api()
    base = Profile(0, 0.7, top_p=0.9, top_k=40)
    same_budget_temp_different_sampler = replace(base, top_p=0.8)

    assert campaign._profile_key(base) == fingerprint(base)
    assert campaign._profile_key(same_budget_temp_different_sampler) == fingerprint(
        same_budget_temp_different_sampler
    )
    assert campaign._profile_key(base) != campaign._profile_key(
        same_budget_temp_different_sampler
    )
