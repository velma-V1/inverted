from inverted.universal_tuning import UNRESTRICTED_THINKING, Profile
from inverted.universal_tuning.scheduler import select_interaction_profile


def test_interaction_tie_handles_unrestricted_without_numeric_coercion() -> None:
    capped = Profile(256, 0.8)
    unrestricted = Profile(UNRESTRICTED_THINKING, 0.8)

    result = select_interaction_profile({
        capped: (1.0, 1.0, 1.0, 1.0, 1.0),
        unrestricted: (1.0, 1.0, 1.0, 1.0, 1.0),
    })

    assert result.status == "INTERACTION_PLATEAU"
    assert result.profile == capped
