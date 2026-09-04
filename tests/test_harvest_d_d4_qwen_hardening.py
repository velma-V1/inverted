import io
import json
from pathlib import Path

import pytest

from inverted.harvest_d.d4_qwen_campaign import D4QwenCampaign
from inverted.harvest_d.d4_qwen_cli import load_d4_config
from inverted.harvest_d.d4_qwen_policy import select_qwen_policy
from inverted.harvest_d.models import ModelResponse


CONFIG = Path("configs/harvest-d-d4-qwen-policy.json")


def _records(default_correct, off_correct, *, default_exhausted=None, off_exhausted=None):
    default_exhausted = default_exhausted or [False] * len(default_correct)
    off_exhausted = off_exhausted or [False] * len(off_correct)
    rows = []
    for index, (d_ok, o_ok) in enumerate(zip(default_correct, off_correct)):
        case_id = f"case-{index:02d}"
        rows.append({
            "case_id": case_id,
            "policy_id": "DEFAULT",
            "semantic_action_correct": bool(d_ok),
            "completion_class": "CONTEXT_EXHAUSTED" if default_exhausted[index] else "SEMANTIC_RESULT",
        })
        rows.append({
            "case_id": case_id,
            "policy_id": "THINK_OFF",
            "semantic_action_correct": bool(o_ok),
            "completion_class": "CONTEXT_EXHAUSTED" if off_exhausted[index] else "SEMANTIC_RESULT",
        })
    return rows


def test_d4_fixed_horizon_freezes_materially_better_operational_policy():
    rows = _records(
        [True] * 6 + [False] * 18,
        [True] * 18 + [False] * 6,
        default_exhausted=[False] * 6 + [True] * 18,
        off_exhausted=[False] * 24,
    )
    result = select_qwen_policy(rows, model_id="qwen3.5:9b-q8_0")
    assert result["state"] == "FROZEN"
    assert result["policy_id"] == "THINK_OFF"
    assert result["evidence_status"] == "DECISIVE"
    assert result["semantic_decision"] == "SUPERIOR"


def test_d4_fixed_horizon_uses_exhaustion_tiebreak_without_claiming_superiority():
    same = [True, False] * 12
    rows = _records(
        same,
        same,
        default_exhausted=[True] * 18 + [False] * 6,
        off_exhausted=[False] * 24,
    )
    result = select_qwen_policy(rows, model_id="qwen3.5:9b-q8_0")
    assert result["state"] == "FROZEN"
    assert result["policy_id"] == "THINK_OFF"
    assert result["evidence_status"] == "PROVISIONAL_FIXED_HORIZON"
    assert result["semantic_decision"] == "NO_DECISIVE_DIFFERENCE"


def test_d4_fixed_horizon_total_tie_defaults_conservatively():
    same = [True, False] * 12
    result = select_qwen_policy(_records(same, same), model_id="qwen3.5:9b-q8_0")
    assert result["state"] == "FROZEN"
    assert result["policy_id"] == "DEFAULT"
    assert result["evidence_status"] == "PROVISIONAL_FIXED_HORIZON"


class _FlatAdapter:
    def __init__(self, model_id: str, *, think_off: bool):
        self.model_id = model_id
        self.calls = 0
        self.generation_options = {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096}
        self.chat_options = {"think": False} if think_off else {}

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            '{"answer":"NOT_THE_ORACLE"}',
            self.model_id,
            100,
            20,
            1.0,
            {"done_reason": "stop", "prompt_eval_count": 100, "eval_count": 20},
        )


def test_d4_campaign_cannot_deadlock_closure_after_full_48_call_gate(tmp_path: Path):
    config = load_d4_config(CONFIG)
    default = _FlatAdapter(config["model"], think_off=False)
    off = _FlatAdapter(config["model"], think_off=True)
    result = D4QwenCampaign(
        tmp_path,
        config=config,
        adapters={"DEFAULT": default, "THINK_OFF": off},
        progress_stream=io.StringIO(),
    ).run()
    assert result.physical_model_calls == 48
    assert result.final_state == "COMPLETE"
    assert result.policy_state == "FROZEN"
    policy = json.loads((tmp_path / "d4_frozen_policy.json").read_text())
    assert policy["policy_id"] == "DEFAULT"
    assert policy["evidence_status"] == "PROVISIONAL_FIXED_HORIZON"


def test_d4_resume_refuses_ambiguous_started_physical_call(tmp_path: Path):
    config = load_d4_config(CONFIG)
    default = _FlatAdapter(config["model"], think_off=False)
    off = _FlatAdapter(config["model"], think_off=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "d4_campaign_journal.jsonl").write_text(
        json.dumps({
            "physical_model_call_id": "ambiguous-call",
            "experiment_id": "D4:ambiguous:DEFAULT",
            "state": "STARTED",
        }) + "\n",
        encoding="utf-8",
    )
    campaign = D4QwenCampaign(
        tmp_path,
        config=config,
        adapters={"DEFAULT": default, "THINK_OFF": off},
        progress_stream=io.StringIO(),
    )
    with pytest.raises(ValueError, match="ambiguous"):
        campaign.run(max_calls=1)
    assert default.calls + off.calls == 0
