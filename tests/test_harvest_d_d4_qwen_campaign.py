import io
import json
from pathlib import Path

from inverted.harvest_d.d4_qwen_campaign import D4QwenCampaign, build_d4_plan
from inverted.harvest_d.d4_qwen_cli import load_d4_config
from inverted.harvest_d.models import ModelResponse


CONFIG = Path("configs/harvest-d-d4-qwen-policy.json")


class _PolicyAdapter:
    def __init__(self, model_id: str, *, think_off: bool):
        self.model_id = model_id
        self.think_off = think_off
        self.calls = 0
        self.generation_options = {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096}
        self.chat_options = {"think": False} if think_off else {}

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        if self.think_off:
            # D4 unit test only verifies one-attempt accounting/package shape.
            text = '{"answer":"USE_CURRENT"}'
            raw = {"done_reason": "stop", "prompt_eval_count": 100, "eval_count": 20}
            return ModelResponse(text, self.model_id, 100, 20, 1.0, raw)
        raw = {"done_reason": "length", "prompt_eval_count": 100, "eval_count": 3996}
        return ModelResponse("", self.model_id, 100, 3996, 1.0, raw)


def test_d4_plan_is_24_matched_cases_two_policies_with_48_call_ceiling():
    config = load_d4_config(CONFIG)
    plan = build_d4_plan(config)
    assert plan.max_calls == 48
    assert len(plan.case_ids) == 24
    assert plan.planned_physical_calls == 48
    assert {row.policy_id for row in plan.experiments} == {"DEFAULT", "THINK_OFF"}
    by_case = {}
    for row in plan.experiments:
        by_case.setdefault(row.case.case_id, set()).add(row.policy_id)
    assert all(policies == {"DEFAULT", "THINK_OFF"} for policies in by_case.values())


def test_d4_model_free_package_uses_zero_calls(tmp_path: Path):
    config = load_d4_config(CONFIG)
    campaign = D4QwenCampaign(tmp_path, config=config, progress_stream=io.StringIO())
    result = campaign.run_model_free()
    assert result.physical_model_calls == 0
    master = json.loads((tmp_path / "00-HARVEST-D-D4-QWEN-POLICY-MASTER-INDEX.json").read_text())
    policy = json.loads((tmp_path / "d4_frozen_policy.json").read_text())
    assert master["physical_model_calls"] == 0
    assert master["max_calls"] == 48
    assert policy["state"] == "NOT_RUN"


def test_d4_physical_execution_never_retries(tmp_path: Path):
    config = load_d4_config(CONFIG)
    default = _PolicyAdapter(config["model"], think_off=False)
    think_off = _PolicyAdapter(config["model"], think_off=True)
    campaign = D4QwenCampaign(
        tmp_path,
        config=config,
        adapters={"DEFAULT": default, "THINK_OFF": think_off},
        progress_stream=io.StringIO(),
    )
    result = campaign.run(max_calls=4)
    assert result.physical_model_calls == 4
    assert default.calls + think_off.calls == 4
    ledger = [json.loads(line) for line in (tmp_path / "d4_call_ledger.jsonl").read_text().splitlines() if line]
    assert len(ledger) == 4
    assert all(row["attempt"] == 1 for row in ledger)
