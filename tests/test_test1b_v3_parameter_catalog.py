from __future__ import annotations

from dataclasses import fields
from math import prod

import inverted.universal_tuning as tuning
from inverted.universal_tuning.core import Profile


def _api():
    assert hasattr(tuning, "ParameterAxis")
    assert hasattr(tuning, "ProfileScreenCandidate")
    assert hasattr(tuning, "parameter_catalog")
    assert hasattr(tuning, "plan_profile_screen")
    return (
        tuning.ParameterAxis,
        tuning.ProfileScreenCandidate,
        tuning.parameter_catalog,
        tuning.plan_profile_screen,
    )


def _profile() -> Profile:
    return Profile(
        thinking_budget=0,
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        min_p=0.05,
        typical_p=0.95,
        repeat_last_n=128,
        repeat_penalty=1.1,
        presence_penalty=0.5,
        frequency_penalty=0.25,
        final_max_tokens=768,
        num_ctx=8192,
    )


def test_catalog_covers_every_profile_field_plus_seed_and_native_effort() -> None:
    _, _, parameter_catalog, _ = _api()
    catalog = parameter_catalog()

    profile_fields = {field.name for field in fields(Profile)}
    catalog_profile_fields = {
        axis.name for axis in catalog if axis.control_path == "PROFILE"
    }
    assert catalog_profile_fields == profile_fields

    external = {
        axis.name: axis for axis in catalog if axis.control_path != "PROFILE"
    }
    assert external["inference_seed"].control_path == "INFERENCE_ARGUMENT"
    assert external["native_thinking_effort"].control_path == "CAPABILITY"
    assert external["native_thinking_effort"].strategy == "CAPABILITY_PROBE"


def test_catalog_has_no_implicit_or_unclassified_strategy() -> None:
    _, _, parameter_catalog, _ = _api()
    catalog = parameter_catalog()

    assert len({axis.name for axis in catalog}) == len(catalog)
    assert all(axis.category for axis in catalog)
    assert all(axis.rationale for axis in catalog)
    assert {axis.strategy for axis in catalog} <= {
        "SWEEP",
        "CONDITIONAL",
        "TASK_BOUND",
        "RUNTIME_DISCOVERY",
        "SUPPORT_PROBE",
        "CAPABILITY_PROBE",
        "SEED_REPLICATION",
    }


def test_temperature_screen_uses_approved_broad_values_before_refinement() -> None:
    _, _, parameter_catalog, _ = _api()
    by_name = {axis.name: axis for axis in parameter_catalog()}

    assert by_name["temperature"].candidates == (
        0.0,
        0.1,
        0.2,
        0.35,
        0.5,
        0.7,
        0.9,
        1.1,
    )
    assert by_name["temperature"].strategy == "SWEEP"
    assert by_name["thinking_budget"].candidates == (
        0,
        256,
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
    )


def test_profile_screen_is_one_factor_at_a_time_not_cartesian() -> None:
    _, _, parameter_catalog, plan_profile_screen = _api()
    incumbent = _profile()
    candidates = plan_profile_screen(incumbent, supports_thinking=True)

    assert candidates
    assert len({candidate.candidate_id for candidate in candidates}) == len(candidates)
    for candidate in candidates:
        changed = [
            field.name
            for field in fields(Profile)
            if getattr(candidate.profile, field.name) != getattr(incumbent, field.name)
        ]
        assert changed == [candidate.axis_name]

    sweep_axes = [
        axis for axis in parameter_catalog()
        if axis.control_path == "PROFILE" and axis.strategy == "SWEEP"
    ]
    cartesian_size = prod(max(1, len(axis.candidates)) for axis in sweep_axes)
    assert len(candidates) == sum(
        sum(value != getattr(incumbent, axis.name) for value in axis.candidates)
        for axis in sweep_axes
    )
    assert len(candidates) < 100
    assert cartesian_size > len(candidates) * 1000


def test_direct_only_model_never_schedules_positive_thinking_budget() -> None:
    _, _, _, plan_profile_screen = _api()
    candidates = plan_profile_screen(_profile(), supports_thinking=False)

    thinking = [item for item in candidates if item.axis_name == "thinking_budget"]
    assert thinking == []
    assert all(item.profile.thinking_budget == 0 for item in candidates)


def test_non_sweep_controls_are_explicit_but_not_unsafely_auto_varied() -> None:
    _, _, parameter_catalog, plan_profile_screen = _api()
    by_name = {axis.name: axis for axis in parameter_catalog()}
    planned_axes = {item.axis_name for item in plan_profile_screen(_profile(), supports_thinking=True)}

    expected = {
        "num_keep": "CONDITIONAL",
        "num_ctx": "RUNTIME_DISCOVERY",
        "num_batch": "RUNTIME_DISCOVERY",
        "num_gpu": "RUNTIME_DISCOVERY",
        "main_gpu": "RUNTIME_DISCOVERY",
        "use_mmap": "RUNTIME_DISCOVERY",
        "num_thread": "RUNTIME_DISCOVERY",
        "draft_num_predict": "RUNTIME_DISCOVERY",
        "stop": "TASK_BOUND",
        "truncate": "SUPPORT_PROBE",
        "shift": "SUPPORT_PROBE",
        "logprobs": "SUPPORT_PROBE",
        "top_logprobs": "SUPPORT_PROBE",
    }
    for name, strategy in expected.items():
        assert by_name[name].strategy == strategy
        assert name not in planned_axes


def test_behavior_axes_are_grouped_for_later_interaction_analysis() -> None:
    _, _, parameter_catalog, _ = _api()
    by_name = {axis.name: axis for axis in parameter_catalog()}

    assert by_name["thinking_budget"].category == "REASONING"
    assert by_name["temperature"].category == "SAMPLER"
    assert by_name["top_p"].category == "SAMPLER"
    assert by_name["repeat_penalty"].category == "REPETITION"
    assert by_name["final_max_tokens"].category == "COMPLETION"
    assert by_name["num_ctx"].category == "RUNTIME"
    assert by_name["logprobs"].category == "OBSERVABILITY"
