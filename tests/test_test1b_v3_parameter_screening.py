from __future__ import annotations

import json

import pytest

import inverted.universal_tuning as tuning
from inverted.universal_tuning.core import AtomicTask, Profile, profile_fingerprint
from inverted.universal_tuning.runner import AdapterCompletion, UniversalRunner
from inverted.universal_tuning.scheduler import AdaptiveScheduler, ModelMetadata
from inverted.universal_tuning.tasks import TASK_FAMILIES, TaskPool


BEHAVIOR_AXES = {
    "top_p",
    "top_k",
    "min_p",
    "presence_penalty",
    "repeat_penalty",
    "typical_p",
    "repeat_last_n",
    "frequency_penalty",
}


def _api():
    required = (
        "ParameterScreenDecision",
        "ParameterScreenResult",
        "plan_behavior_screen",
        "parameter_screen_call_geometry",
        "screen_profile_parameters",
    )
    for name in required:
        assert hasattr(tuning, name), name
    return tuple(getattr(tuning, name) for name in required)


def _single_family_pool(count: int = 720) -> TaskPool:
    family = "EXTRACTION"
    return TaskPool(
        seed=20260908,
        tasks=tuple(
            AtomicTask(
                task_id=f"{family}:{index:04d}",
                family=family,
                difficulty=index % 4 + 1,
                prompt="Return OK.",
                expected="OK",
                scorer="exact_value",
            )
            for index in range(count)
        ),
    )


def _full_pool(count: int = 720) -> TaskPool:
    return TaskPool(
        seed=20260908,
        tasks=tuple(
            AtomicTask(
                task_id=f"{family}:{index:04d}",
                family=family,
                difficulty=index % 4 + 1,
                prompt="Return OK.",
                expected="OK",
                scorer="exact_value",
            )
            for family in TASK_FAMILIES
            for index in range(count)
        ),
    )


def test_screen_stage_is_a_fresh_sixth_120_task_partition() -> None:
    scheduler = AdaptiveScheduler(_single_family_pool(), ModelMetadata())
    family = "EXTRACTION"
    old_stages = ("gate", "budget", "temperature", "interaction", "holdout")
    old_ids = {
        task_id
        for stage in old_stages
        for task_id in scheduler.partition_task_ids(family, stage, 120)
    }
    screen_ids = set(scheduler.partition_task_ids(family, "screen", 120))

    assert len(old_ids) == 600
    assert len(screen_ids) == 120
    assert old_ids.isdisjoint(screen_ids)
    assert min(int(task_id.rsplit(":", 1)[1]) for task_id in screen_ids) == 600


def test_behavior_screen_excludes_controls_with_dedicated_objectives() -> None:
    _, _, plan_behavior_screen, _, _ = _api()
    incumbent = Profile(1024, 0.7)
    candidates = plan_behavior_screen(incumbent, supports_thinking=True)

    assert {item.axis_name for item in candidates} == BEHAVIOR_AXES
    assert all(item.axis_name not in {
        "thinking_budget", "temperature", "final_max_tokens",
        "num_ctx", "inference_seed", "native_thinking_effort",
    } for item in candidates)


def test_screen_geometry_is_bounded_and_accounts_for_thinking_double_calls() -> None:
    _, _, _, geometry, _ = _api()
    direct = geometry(Profile(0, 0.7), supports_thinking=False)
    thinking = geometry(Profile(1024, 0.7), supports_thinking=True)

    assert direct["candidate_count"] == 40
    assert direct["discovery_atomic_per_candidate"] == 40
    assert direct["confirmation_atomic_max_per_candidate"] == 120
    assert direct["discovery_physical_ceiling"] == 640
    assert direct["worst_case_physical_ceiling"] == 2560
    assert thinking["candidate_count"] == 40
    assert thinking["discovery_physical_ceiling"] == 1280
    assert thinking["worst_case_physical_ceiling"] == 5120


class _ProfileSensitiveAdapter:
    metadata = ModelMetadata()

    @staticmethod
    def _success_limit(profile: Profile) -> int:
        limit = 6
        if profile.top_p == 0.7:
            limit = 3
        elif profile.top_p == 0.8:
            limit = 8
        if profile.top_p == 0.8 and profile.top_k == 20:
            limit = 10
        return limit

    def complete(self, tasks, profile: Profile, inference_seed: int) -> AdapterCompletion:
        limit = self._success_limit(profile)
        responses = []
        for task in tasks:
            index = int(task.task_id.rsplit(":", 1)[1])
            answer = "OK" if index % 10 < limit else "WRONG"
            responses.append(json.dumps({"answer": answer}))
        physical_calls = 2 if profile.thinking else 1
        return AdapterCompletion(
            responses=tuple(responses),
            latency_s=0.01 * len(tasks),
            output_tokens=4 * len(tasks),
            thinking_tokens=profile.thinking_budget if profile.thinking else 0,
            physical_calls=physical_calls,
            raw_calls=tuple(
                {"inference_seed": inference_seed, "profile": profile_fingerprint(profile)}
                for _ in range(physical_calls)
            ),
        )


def _runner(tmp_path):
    pool = _full_pool()
    runner = UniversalRunner(
        tmp_path,
        pool,
        _ProfileSensitiveAdapter(),
        {"task_pool_sha256": pool.manifest_hash, "protocol": "screen-red-contract"},
        max_physical_calls=10000,
    )
    return runner, AdaptiveScheduler(pool, ModelMetadata())


def test_screen_promotes_only_independently_confirmed_winner_and_rebases_next_axis(tmp_path) -> None:
    Decision, Result, _, geometry, screen = _api()
    runner, scheduler = _runner(tmp_path)
    incumbent = Profile(0, 0.7, top_p=0.9, top_k=40)

    result = screen(
        runner,
        scheduler,
        incumbent,
        supports_thinking=False,
        axis_names=("top_p", "top_k"),
        max_additional_physical_calls=1000,
    )

    assert isinstance(result, Result)
    assert result.incumbent.top_p == 0.8
    assert result.incumbent.top_k == 20
    assert all(isinstance(item, Decision) for item in result.decisions)
    promoted = [item for item in result.decisions if item.promoted]
    assert [(item.axis_name, item.axis_value) for item in promoted] == [
        ("top_p", 0.8),
        ("top_k", 20),
    ]
    assert all(item.scout_atomic == 40 for item in result.decisions)
    assert all(item.scout_status in {"SUPERIOR", "INFERIOR", "EQUIVALENT", "CLOSE", "TIE_OR_PLATEAU"}
               for item in result.decisions)
    assert all(item.confirmation_atomic >= 40 for item in promoted)
    assert all(item.confirmation_status == "SUPERIOR" for item in promoted)
    assert all(item.incumbent_fingerprint != item.candidate_fingerprint for item in result.decisions)

    top_k_winner = next(item for item in promoted if item.axis_name == "top_k")
    expected_top_k_baseline = Profile(0, 0.7, top_p=0.8, top_k=40)
    assert top_k_winner.incumbent_fingerprint == profile_fingerprint(expected_top_k_baseline)

    rows = runner.store.observation_rows()
    assert rows
    assert {row["stage"] for row in rows} == {"screen"}
    assert result.physical_calls <= geometry(incumbent, supports_thinking=False)["worst_case_physical_ceiling"]


def test_screen_budget_fails_before_transport_when_next_block_cannot_fit(tmp_path) -> None:
    _, _, _, _, screen = _api()
    runner, scheduler = _runner(tmp_path)

    with pytest.raises(RuntimeError, match="screen.*ceiling"):
        screen(
            runner,
            scheduler,
            Profile(0, 0.7, top_p=0.9),
            supports_thinking=False,
            axis_names=("top_p",),
            max_additional_physical_calls=1,
        )

    assert runner.store.physical_calls_used() == 0
