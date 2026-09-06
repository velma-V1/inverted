import dataclasses
import json

from inverted_brain.config import QWEN_MODEL, QWEN_OPTIONS, CAMPAIGN_RUN_CEILING
from inverted_brain.contracts import (
    AgentEvent,
    DifficultyVector,
    MechanismCandidate,
    TrialResult,
)


def test_qwen_runtime_is_preregistered():
    assert QWEN_MODEL == "qwen3.5:9b-q8_0"
    assert QWEN_OPTIONS["temperature"] == 0.7
    assert QWEN_OPTIONS["top_p"] == 0.8
    assert QWEN_OPTIONS["top_k"] == 20
    assert QWEN_OPTIONS["min_p"] == 0.0
    assert QWEN_OPTIONS["presence_penalty"] == 1.5
    assert QWEN_OPTIONS["repeat_penalty"] == 1.0
    assert CAMPAIGN_RUN_CEILING == 200


def test_contracts_are_serializable_and_isolated():
    difficulty = DifficultyVector(constraints=2, dependency_depth=3)
    event = AgentEvent(index=0, kind="observation", actor="QWEN_BRAIN", data={"file": "a.txt"})
    trial = TrialResult(
        trial_id="t1", arm="QWEN_BRAIN", status="COMPLETE",
        outcome_passed=False, process_passed=True, events=[event],
    )
    candidate = MechanismCandidate(
        candidate_id="m1", trigger="after mutation", baseline_behavior="assume",
        replacement_behavior="reconcile", evidence_ids=["t1"], scope=["stale_state"],
    )
    assert dataclasses.asdict(difficulty)["dependency_depth"] == 3
    assert json.loads(json.dumps(dataclasses.asdict(trial)))["events"][0]["kind"] == "observation"
    assert dataclasses.asdict(candidate)["status"] == "proposed"


def test_new_package_does_not_import_original_inverted():
    import inspect
    import inverted_brain.contracts as contracts
    source = inspect.getsource(contracts)
    assert "from inverted." not in source
    assert "import inverted." not in source
