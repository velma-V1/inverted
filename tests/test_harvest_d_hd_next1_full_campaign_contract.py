from __future__ import annotations

import json
from pathlib import Path
import re

from inverted.harvest_d.hd_next1_authorization import authorize_hd_next1_execution
from inverted.harvest_d.hd_next1_campaign import HDNext1Campaign
from inverted.harvest_d.hd_next1_config import load_hd_next1_config
from inverted.harvest_d.hd_next1_local_search import LOCAL_SEARCH_RULE_HASH
from inverted.harvest_d.hd_next1_preregistration import build_preregistration_package
from inverted.harvest_d.models import ModelResponse


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "harvest-d-hd-next-1.json"


class DeterministicFakeAdapter:
    generation_options = {"temperature": 0.0, "seed": 20260902, "num_ctx": 4096}

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.calls = 0

    @staticmethod
    def _answer_for_case(prompt: str) -> str:
        match = re.search(r"D3 controlled decision case (\d+)\.(\d+)", prompt)
        if not match:
            raise AssertionError("synthetic HD-NEXT-1 prompt lost D3 case identity")
        family = int(match.group(1))
        index = int(match.group(2))
        fixed = {
            1: "USE_CURRENT",
            3: "FOLLOW_CANONICAL",
            4: "DO_PARENT_FIRST",
            7: "TRUST_VERIFIER",
            8: "REPLAN",
            10: "REJECT_LOCAL_FIX",
            11: "INVESTIGATE",
        }
        if family in fixed:
            return fixed[family]
        if family == 2:
            return "REQUEST_EVIDENCE" if index % 2 == 1 else "EXECUTE_NOW"
        if family == 5:
            return "ESCALATE_SCOPE" if index % 2 == 1 else "EXECUTE_SCOPED"
        if family == 6:
            return "RECONCILE" if index % 2 == 1 else "START_NEW"
        if family == 9:
            return "QWEN_STANDARD" if index % 2 == 1 else "ROUTINE_LOCAL"
        raise AssertionError(f"unknown synthetic D3 family {family}")

    def complete(self, prompt: str, system: str | None = None) -> ModelResponse:
        self.calls += 1
        answer = self._answer_for_case(prompt)
        return ModelResponse(
            text=json.dumps({"answer": answer}),
            model=self.model_id,
            input_tokens=10,
            output_tokens=4,
            latency_ms=0.1,
            raw={"done_reason": "stop"},
        )


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_complete_fake_campaign_uses_exact_frozen_budget_and_compiles_three_questions(tmp_path):
    cfg = load_hd_next1_config(CONFIG)
    prereg = tmp_path / "prereg"
    build_preregistration_package(REPO, prereg, cfg)
    owner = authorize_hd_next1_execution(prereg, owner_approved=True)
    small = DeterministicFakeAdapter("SMALL_A-test")
    qwen = DeterministicFakeAdapter("QWEN-test")
    run = tmp_path / "run"
    result = HDNext1Campaign(
        run,
        prereg_root=prereg,
        config=cfg,
        adapters={"SMALL_A": small, "QWEN": qwen},
        owner_authorization=owner,
    ).run_authorized()

    assert result.physical_model_calls == 672
    assert result.final_state == "COMPLETE"
    assert small.calls == 576
    assert qwen.calls == 96

    requests = _jsonl(run / "raw_model_requests.jsonl")
    assert sum(row["model_key"] == "QWEN" and row["stage"] == "T1_CALIBRATION" for row in requests) == 12
    assert sum(row["model_key"] == "QWEN" and row["stage"] == "T4T5_QWEN_DISCRIMINATION" for row in requests) == 21
    assert sum(row["model_key"] == "QWEN" and row["stage"].startswith("T6_") for row in requests) == 63
    assert sum(row["model_key"] == "SMALL_A" and row["stage"] == "T2_SMALL_A_SCREEN" for row in requests) == 216
    assert sum(row["model_key"] == "SMALL_A" and row["stage"] == "T3_LOCAL_MINIMALITY" for row in requests) == 96
    assert sum(row["model_key"] == "SMALL_A" and row["stage"].startswith("T6_") for row in requests) == 252

    freeze = json.loads((run / "development_freeze.json").read_text())
    assert freeze["local_search_rule_hash"] == LOCAL_SEARCH_RULE_HASH
    assert freeze["retained_components"]
    assert set(freeze["protected_treatments"]) == {
        "CONFIRM_PROMOTED_POLICY",
        "CONFIRM_RAW_BASELINE",
        "CONFIRM_STRONGEST_CHALLENGER",
        "CONFIRM_NEGATIVE_TRANSFER_CONTROL",
    }

    decisions = json.loads((run / "final_architecture_decisions.json").read_text())
    assert set(decisions) == {
        "Q-MODEL-SUBSTITUTION",
        "Q-MINIMUM-SUPPORT",
        "Q-NEGATIVE-TRANSFER-BOUNDARY",
    }

    normalized = _jsonl(run / "normalized_model_calls.jsonl")
    fresh_positions = [row["execution_position"] for row in normalized if row["stage"] == "T6_FRESH_CONFIRMATION"]
    sealed_positions = [row["execution_position"] for row in normalized if row["stage"] == "T6_SEALED_CONFIRMATION"]
    assert fresh_positions == sorted(fresh_positions)
    assert sealed_positions == sorted(sealed_positions)
    assert max(fresh_positions) < min(sealed_positions) or set(fresh_positions).isdisjoint(sealed_positions)
