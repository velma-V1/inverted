import json
from functools import lru_cache

from inverted.universal_tuning.campaign import ExperimentSpec, run_universal_campaign
from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.runner import AdapterCompletion
from inverted.universal_tuning.tasks import TaskPool, build_qwen_task_pool


@lru_cache(maxsize=1)
def _arithmetic_pool():
    full = build_qwen_task_pool(seed=20260907, per_family=600)
    tasks = tuple(task for task in full.tasks if task.family == "ARITHMETIC")
    return TaskPool(seed=full.seed, tasks=tasks)


def _stage(task_id):
    index = int(task_id.rsplit("-", 1)[1])
    return ("gate", "budget", "temperature", "interaction", "holdout")[index // 120]


class SurfaceAdapter:
    def __init__(self, accuracy, contract_rate=lambda stage, profile: 1.0):
        self.accuracy = accuracy
        self.contract_rate = contract_rate
        self.metadata = __import__(
            "inverted.universal_tuning.scheduler", fromlist=["ModelMetadata"]
        ).ModelMetadata()

    def complete(self, tasks, profile, seed):
        responses = []
        for task in tasks:
            stage = _stage(task.task_id)
            local = int(task.task_id.rsplit("-", 1)[1]) % 120
            rank = local % 40
            semantic_ok = rank < round(self.accuracy(stage, profile) * 40)
            contract_ok = rank < round(self.contract_rate(stage, profile) * 40)
            answer = task.expected if semantic_ok else -999999
            key = "answer" if contract_ok else "result"
            responses.append(json.dumps({key: answer}))
        physical = 2 if profile.thinking else 1
        return AdapterCompletion(
            tuple(responses), 0.01 * physical, len(tasks) * 5,
            min(profile.thinking_budget, 700), physical,
            tuple({"synthetic": True, "call": i} for i in range(physical)),
        )


def _spec(**overrides):
    values = dict(
        families=("ARITHMETIC",), hard_call_ceiling=2500,
        coarse_temperatures=(0.2, 0.4, 0.6, 0.8, 1.0, 1.2),
        budget_candidates=(256, 512, 1024, 2048),
        tasks_per_family=600, parameter_screen_enabled=False,
    )
    values.update(overrides)
    return ExperimentSpec(**values)


def test_broad_plateau_and_minimum_budget_are_reported_without_fake_optimum(tmp_path):
    def accuracy(stage, profile):
        if not profile.thinking:
            return 0.60
        if stage == "budget":
            return 0.75 if profile.thinking_budget < 512 else 0.90
        return 0.90
    result = run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy), _spec()
    )
    policy = result.policy["ARITHMETIC"]
    assert policy["minimum_useful_budget"] == 512
    assert policy["temperature"]["kind"] == "PLATEAU"
    assert policy["temperature"]["optimum"] is None
    assert policy["temperature"]["lower"] <= 0.6
    assert policy["temperature"]["upper"] >= 0.8
    assert policy["holdout_atomic"] >= 40
    assert (tmp_path / "operating-surface.json").exists()
    assert (tmp_path / "report.md").exists()


def test_narrow_temperature_optimum_is_resolved_only_by_semantics(tmp_path):
    def accuracy(stage, profile):
        if not profile.thinking:
            return 0.55
        if stage == "budget":
            return 0.70 if profile.thinking_budget < 512 else 0.95
        if stage in {"temperature", "interaction", "holdout"}:
            return 0.95 if abs(profile.temperature - 0.600) < 1e-9 else 0.75
        return 0.95
    result = run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy), _spec()
    )
    surface = result.policy["ARITHMETIC"]["temperature"]
    assert surface["kind"] == "OPTIMUM"
    assert surface["optimum"] == 0.6
    assert surface["resolution"] <= 0.0011


def test_contract_only_failure_skips_reasoning_tuning(tmp_path):
    def accuracy(stage, profile):
        return 1.0
    def contract(stage, profile):
        return 0.50
    result = run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy, contract), _spec()
    )
    policy = result.policy["ARITHMETIC"]
    assert policy["mode"] == "direct"
    assert policy["status"] == "CONTRACT_LIMITED"
    assert policy["minimum_useful_budget"] is None
    assert policy["temperature"] is None


def test_interaction_stage_can_change_selected_profile(tmp_path):
    def accuracy(stage, profile):
        if not profile.thinking:
            return 0.60
        if stage == "budget":
            return 0.90
        if stage == "temperature":
            return 0.90
        if stage in {"interaction", "holdout"}:
            if profile.thinking_budget == 512 and abs(profile.temperature - 0.8) < 1e-9:
                return 1.0
            return 0.80
        return 0.90
    result = run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy), _spec()
    )
    policy = result.policy["ARITHMETIC"]
    assert policy["interaction"]["changed_by_interaction"] is True
    assert policy["selected_profile"]["thinking_budget"] == 512
    assert policy["selected_profile"]["temperature"] == 0.8


def test_capability_limit_does_not_waste_calls_on_temperature_search(tmp_path):
    def accuracy(stage, profile):
        return 0.20 if not profile.thinking else 0.25
    result = run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy), _spec()
    )
    policy = result.policy["ARITHMETIC"]
    assert policy["mode"] == "unresolved"
    assert policy["status"] == "CAPABILITY_UNRESOLVED"
    assert policy["temperature"] is None
    stages = {json.loads(line)["stage"] for line in (tmp_path / "atomic_observations.jsonl").read_text().splitlines()}
    assert "temperature" not in stages


def test_high_budget_diagnostic_can_reopen_budget_search_without_certifying_itself(tmp_path):
    def accuracy(stage, profile):
        if not profile.thinking:
            return 0.60
        if stage == "gate":
            return 0.95 if profile.thinking_budget >= 2048 else 0.70
        if stage == "budget":
            return 0.92 if profile.thinking_budget >= 1024 else 0.75
        return 0.92
    result = run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy), _spec()
    )
    policy = result.policy["ARITHMETIC"]
    assert policy["mode"] == "thinking"
    assert policy["gate_diagnostic_used"] is True
    assert policy["minimum_useful_budget"] == 1024
    assert policy["selected_profile"]["thinking_budget"] in {1024, 2048}


def test_protocol_manifest_freezes_statistical_decision_rules(tmp_path):
    def accuracy(stage, profile):
        return 1.0
    run_universal_campaign(
        tmp_path, _arithmetic_pool(), SurfaceAdapter(accuracy), _spec()
    )
    document = json.loads((tmp_path / "protocol-v2-manifest.json").read_text())
    manifest = document["manifest"]
    assert manifest["bootstrap_seed"] == 20260907
    assert manifest["bootstrap_iterations"] == 4000
    assert manifest["confidence_level"] == 0.95
    assert manifest["minimum_useful_effect"] == 0.05
    assert manifest["noninferiority_margin"] == -0.02
    assert manifest["acceptable_semantic_floor"] == 0.90
