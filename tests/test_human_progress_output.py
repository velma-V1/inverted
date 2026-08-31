from inverted.cli import _build_class_progress_callback
from inverted.runner import ExperimentConfig, build_trial_plan


class _Model:
    provider = "mock"
    model = "m"


def test_progress_emits_once_per_family_complexity_class_not_per_trial():
    config = ExperimentConfig(
        families=("state", "policy"),
        complexities=(1, 2),
        qualities=(0.2, 0.8),
        seeds=(1, 2),
        epochs=1,
        arms=("C_SYSTEM", "E_RANDOM_AUDITOR"),
    )
    models = [_Model()]
    plan = build_trial_plan(config, models)
    lines = []
    callback = _build_class_progress_callback(config, models, emit=lines.append)

    for completed, item in enumerate(plan, start=1):
        callback(completed, len(plan), item)

    assert len(plan) > len(lines)
    assert len(lines) == 4
    assert sum("family=state complexity=1" in line for line in lines) == 1
    assert sum("family=state complexity=2" in line for line in lines) == 1
    assert sum("family=policy complexity=1" in line for line in lines) == 1
    assert sum("family=policy complexity=2" in line for line in lines) == 1
    assert all("CLASS START" in line for line in lines)
    assert lines[-1].startswith("CLASS PROGRESS [####################] 4/4")
