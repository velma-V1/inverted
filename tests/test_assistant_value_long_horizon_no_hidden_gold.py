from copy import deepcopy

from inverted.assistant_value.long_horizon import (
    derive_system_candidate,
    generate_long_horizon_cases,
)


def test_long_horizon_system_candidate_is_derived_from_public_facts_only():
    cases = generate_long_horizon_cases(seed=20260901, per_horizon=3, horizons=(8, 16))
    for case in cases:
        for step in case["steps"]:
            expected = derive_system_candidate(case, step)
            tampered = deepcopy(case)
            tampered_step = tampered["steps"][step["step_index"]]
            tampered_step["oracle"]["action_id"] = "definitely-not-a-public-action"
            tampered_step["oracle"]["expected_value"] = -999999
            tampered_step["oracle"]["path"] = "hidden.fake.path"
            assert derive_system_candidate(tampered, tampered_step) == expected


def test_long_horizon_system_candidate_matches_public_requirement_when_not_faulted():
    case = generate_long_horizon_cases(seed=77, per_horizon=1, horizons=(8,))[0]
    for step in case["steps"]:
        candidate = derive_system_candidate(case, step, inject_fault=False)
        requirement = step["public"]["requirement"]
        assert candidate["path"] == requirement["path"]
        assert candidate["value"] == requirement["expected"]
        assert candidate["scope"] == "required-only"
