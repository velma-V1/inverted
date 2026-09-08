from __future__ import annotations

import json

import inverted.universal_tuning.campaign as campaign_module
from inverted.universal_tuning.campaign import ExperimentSpec, call_geometry, run_universal_campaign
from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.parameter_screening import ParameterScreenResult
from inverted.universal_tuning.runner import AdapterCompletion
from inverted.universal_tuning.scheduler import ModelMetadata
from inverted.universal_tuning.tasks import TaskPool, build_qwen_task_pool


def _arithmetic_pool_720() -> TaskPool:
    full = build_qwen_task_pool(seed=20260908, per_family=720)
    return TaskPool(
        seed=full.seed,
        tasks=tuple(task for task in full.tasks if task.family == "ARITHMETIC"),
    )


def _stage(task_id: str) -> str:
    index = int(task_id.rsplit("-", 1)[1])
    return ("gate", "budget", "temperature", "interaction", "holdout", "screen")[
        index // 120
    ]


class _ThinkingWinsAdapter:
    metadata = ModelMetadata()

    def __init__(self) -> None:
        self.calls: list[tuple[str, Profile]] = []

    def complete(self, tasks, profile: Profile, inference_seed: int) -> AdapterCompletion:
        stage = _stage(tasks[0].task_id)
        self.calls.append((stage, profile))
        responses = []
        for task in tasks:
            local = int(task.task_id.rsplit("-", 1)[1]) % 40
            success = local < (40 if profile.thinking else 20)
            responses.append(json.dumps({"answer": task.expected if success else -999999}))
        physical = 2 if profile.thinking else 1
        return AdapterCompletion(
            responses=tuple(responses),
            latency_s=0.01 * physical,
            output_tokens=5 * len(tasks),
            thinking_tokens=profile.thinking_budget if profile.thinking else 0,
            physical_calls=physical,
            raw_calls=tuple({"synthetic": True, "seed": inference_seed} for _ in range(physical)),
        )


def test_v3_campaign_reserves_720_frozen_tasks_per_family_and_enables_screening() -> None:
    spec = ExperimentSpec()
    assert spec.tasks_per_family == 720
    assert spec.parameter_screen_enabled is True


def test_call_geometry_accounts_for_mandatory_model_level_parameter_screen() -> None:
    geometry = call_geometry(8)
    assert geometry["base_minimum"] == 48 * 8
    assert geometry["parameter_screen_minimum"] == 640
    assert geometry["minimum"] == 48 * 8 + 640
    assert geometry["base_expected"] == 312 * 8
    assert geometry["parameter_screen_expected"] == 640
    assert geometry["expected"] == 312 * 8 + 640
    assert geometry["base_worst_case"] == 1320 * 8
    assert geometry["parameter_screen_worst_case"] == 2560
    assert geometry["worst_case"] == 1320 * 8 + 2560


def test_screened_sampler_fields_propagate_through_downstream_stages_and_holdout(
    tmp_path, monkeypatch
) -> None:
    selected_base = Profile(0, 0.7, top_p=0.8, top_k=20, repeat_penalty=1.1)
    screen_calls: list[Profile] = []

    def fake_screen(runner, scheduler, incumbent, **kwargs):
        screen_calls.append(incumbent)
        return ParameterScreenResult(
            incumbent=selected_base,
            decisions=(),
            physical_calls=0,
            call_geometry={"worst_case_physical_ceiling": 2560},
        )

    monkeypatch.setattr(campaign_module, "screen_profile_parameters", fake_screen, raising=False)
    adapter = _ThinkingWinsAdapter()
    spec = ExperimentSpec(
        families=("ARITHMETIC",),
        hard_call_ceiling=1200,
        checkpoints=(40,),
        coarse_temperatures=(0.6, 0.8),
        budget_candidates=(256, 512),
        tasks_per_family=720,
    )

    result = run_universal_campaign(tmp_path, _arithmetic_pool_720(), adapter, spec)

    assert len(screen_calls) == 1
    assert screen_calls[0].thinking_budget == 0
    assert result.policy["ARITHMETIC"]["screened_base_profile"]["top_p"] == 0.8
    assert result.policy["ARITHMETIC"]["screened_base_profile"]["top_k"] == 20
    selected = result.policy["ARITHMETIC"]["selected_profile"]
    assert selected["top_p"] == 0.8
    assert selected["top_k"] == 20
    assert selected["repeat_penalty"] == 1.1

    downstream = [
        profile
        for stage, profile in adapter.calls
        if stage in {"budget", "temperature", "interaction", "holdout"}
    ]
    assert downstream
    assert all(profile.top_p == 0.8 for profile in downstream)
    assert all(profile.top_k == 20 for profile in downstream)
    assert all(profile.repeat_penalty == 1.1 for profile in downstream)


def test_screen_executes_before_any_protected_holdout_call(tmp_path, monkeypatch) -> None:
    order: list[str] = []

    def fake_screen(runner, scheduler, incumbent, **kwargs):
        order.append("screen")
        return ParameterScreenResult(
            incumbent=Profile(0, 0.7, top_p=0.8),
            decisions=(),
            physical_calls=0,
            call_geometry={"worst_case_physical_ceiling": 2560},
        )

    monkeypatch.setattr(campaign_module, "screen_profile_parameters", fake_screen, raising=False)

    class _OrderedAdapter(_ThinkingWinsAdapter):
        def complete(self, tasks, profile, inference_seed):
            stage = _stage(tasks[0].task_id)
            if stage == "holdout" and "holdout" not in order:
                order.append("holdout")
            return super().complete(tasks, profile, inference_seed)

    run_universal_campaign(
        tmp_path,
        _arithmetic_pool_720(),
        _OrderedAdapter(),
        ExperimentSpec(
            families=("ARITHMETIC",), hard_call_ceiling=1200,
            checkpoints=(40,), coarse_temperatures=(0.6, 0.8),
            budget_candidates=(256, 512), tasks_per_family=720,
        ),
    )

    assert order[:2] == ["screen", "holdout"]
