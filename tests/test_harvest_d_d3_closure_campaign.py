import io
import json
from pathlib import Path

from inverted.harvest_d.d3_closure_campaign import D3ClosureCampaign, build_closure_plan
from inverted.harvest_d.d3_closure_cases import generate_closure_cases
from inverted.harvest_d.d3_closure_cli import load_closure_config
from inverted.harvest_d.models import ModelResponse


CONFIG = Path("configs/harvest-d-d3-closure-v2.json")


class _FakeAdapter:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.calls = 0
        self.generation_options = {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096}

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            text='{"answer":"USE_CURRENT"}',
            model=self.model_id,
            input_tokens=100,
            output_tokens=20,
            latency_ms=1.0,
            raw={"done_reason": "stop", "prompt_eval_count": 100, "eval_count": 20},
        )


def test_closure_partitions_are_fresh_and_disjoint():
    dev = generate_closure_cases("closure-development", seed=20261103, per_family=1)
    fresh = generate_closure_cases("closure-fresh", seed=20261113, per_family=1)
    sealed = generate_closure_cases("closure-sealed", seed=20261203, per_family=1)
    assert all(case.case_id.startswith("closure-dev-") for case in dev)
    assert all(case.case_id.startswith("closure-fresh-") for case in fresh)
    assert all(case.case_id.startswith("closure-sealed-") for case in sealed)
    ids = [case.case_id for case in (*dev, *fresh, *sealed)]
    assert len(ids) == len(set(ids))
    assert {case.metadata["partition"] for case in dev} == {"closure-development"}


def test_plan_respects_200_call_ceiling_and_protected_confirmation():
    config = load_closure_config(CONFIG)
    plan = build_closure_plan(config)
    assert plan.max_calls == 200
    assert plan.sealed_reserve == 48
    assert len([x for x in plan.experiments if x.block == "C7"]) <= 48
    assert all(x.sealed for x in plan.experiments if x.block == "C7")
    assert not any(x.sealed for x in plan.experiments if x.block != "C7")
    assert plan.planned_physical_calls <= 200


def test_model_free_campaign_writes_zero_call_package_and_progress(tmp_path: Path):
    config = load_closure_config(CONFIG)
    stream = io.StringIO()
    campaign = D3ClosureCampaign(tmp_path, config=config, progress_stream=stream)
    result = campaign.run_model_free()
    assert result.physical_model_calls == 0
    assert result.final_state == "MODEL_FREE_COMPLETE"
    assert (tmp_path / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json").exists()
    master = json.loads((tmp_path / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json").read_text())
    assert master["protocol"] == "D3-CLOSURE-v2"
    assert master["physical_model_calls"] == 0
    assert master["max_calls"] == 200
    assert master["sealed_reserve"] == 48
    assert "0/" in stream.getvalue()


def test_fake_physical_run_uses_exactly_one_attempt_per_scheduled_call(tmp_path: Path):
    config = load_closure_config(CONFIG)
    small = _FakeAdapter(config["models"]["SMALL_A"])
    qwen = _FakeAdapter(config["models"]["QWEN"])
    campaign = D3ClosureCampaign(
        tmp_path,
        config=config,
        adapters={"SMALL_A": small, "QWEN": qwen},
        progress_stream=io.StringIO(),
    )
    result = campaign.run(max_calls=2)
    assert result.physical_model_calls == 2
    assert small.calls + qwen.calls == 2
    ledger = [json.loads(line) for line in (tmp_path / "closure_call_ledger.jsonl").read_text().splitlines() if line]
    assert len(ledger) == 2
    assert all(row["attempt"] == 1 for row in ledger)
