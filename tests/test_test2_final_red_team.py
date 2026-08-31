from __future__ import annotations

from collections import Counter, defaultdict
from types import SimpleNamespace

import pytest

import inverted.test2_local_impl as local_impl
from inverted.models import MockModelAdapter, ModelCallError
from inverted.test2_integrity import attach_repair_validator_outcomes, harden_evidence_integrity
from inverted.test2_local import BoundedModelCaller, LOCAL_MODELS, run_local_campaign
from inverted.test2_metadata import enrich_test2_evidence
from inverted.test2_preregistration import evaluate_primary_verdict
from inverted.test2_types import PhysicalCallBudget


CONDITIONS = {("raw", "regenerate"), ("raw", "targeted"), ("structured", "regenerate"), ("structured", "targeted")}


def _evidence_with_calls(model_calls: list[dict]):
    prompt = {"call_identity": "same", "model": "m", "role": "executor", "messages": [{"role": "user", "content": "x"}], "serialized": "x"}
    response = {"call_identity": "same", "model": "m", "role": "executor", "text": "{}"}
    return {
        "master_index": {"mode": "local", "physical_model_calls": 1},
        "raw": {
            "trials": [], "model_calls": model_calls,
            "prompts": [prompt, dict(prompt)], "responses": [response, dict(response)],
            "candidates": [], "events": [], "validator_results": [], "repairs": [],
        },
        "effects": {}, "order": {}, "models": {}, "thresholds": {},
        "provenance": {"config": {"local": {"models": list(LOCAL_MODELS)}}, "models": {"identity_match": True}},
    }


def _proper_primary_rows(*, cached: bool = False):
    rows = []
    physical = 0
    for task_index in range(6):
        task = f"task-{task_index}"
        for model_index in range(3):
            model = f"m{model_index}"
            for feedback, strategy, success in (
                ("structured", "targeted", True),
                ("raw", "regenerate", False),
            ):
                physical += 1
                is_cached = cached and feedback == "structured" and task_index == 0 and model_index == 0
                rows.append({
                    "phase": "repair_factorial", "role": "repairer", "model": model, "task_id": task,
                    "feedback_style": feedback, "strategy": strategy, "success": success, "catastrophic": False,
                    "call_identity": f"call-{physical}", "cache_hit": is_cached,
                    "physical_call_number": None if is_cached else physical,
                })
    return rows


def test_primary_contract_rejects_18_rows_that_are_not_three_by_six_cartesian_grid():
    rows = []
    for i in range(18):
        for feedback, strategy, success in (
            ("structured", "targeted", True),
            ("raw", "regenerate", False),
        ):
            rows.append({
                "model": "only-one-model", "task_id": f"task-{i}",
                "feedback_style": feedback, "strategy": strategy,
                "success": success, "catastrophic": False,
                "call_identity": f"{feedback}-{i}", "cache_hit": False,
                "physical_call_number": i + (1 if feedback == "structured" else 101),
            })
    result = evaluate_primary_verdict(rows)
    assert result["verdict"] == "NON-DECISIVE"
    assert result.get("models") == 1
    assert result.get("tasks") == 18


def test_primary_contract_requires_every_preregistered_cell_to_be_a_distinct_physical_call():
    result = evaluate_primary_verdict(_proper_primary_rows(cached=True))
    assert result["verdict"] == "NON-DECISIVE"
    assert "physical" in result["reason"].lower() or "cache" in result["reason"].lower()


def test_legitimate_cache_reuse_is_not_misclassified_as_duplicate_physical_identity():
    evidence = _evidence_with_calls([
        {"call_identity": "same", "model": "m", "role": "executor", "cache_hit": False, "physical_call_number": 1},
        {"call_identity": "same", "model": "m", "role": "executor", "cache_hit": True, "physical_call_number": None},
    ])
    enrich_test2_evidence(evidence)
    harden_evidence_integrity(evidence)
    audit = evidence["diagnostics"]["contamination_audit"]
    assert audit["unique_model_call_identity"] is True
    assert audit["cache_identity_reference_integrity"] is True
    assert audit["physical_call_number_integrity"] is True


def test_repair_screen_is_condition_balanced_disjoint_and_task_spread():
    result = run_local_campaign(
        [MockModelAdapter(model=model) for model in LOCAL_MODELS],
        run_id="final-red-team-screen",
        hard_limit=480,
    )
    screen = [row for row in result["records"] if row.get("phase") == "repair_screen"]
    primary = [row for row in result["records"] if row.get("phase") == "repair_factorial"]
    assert screen and primary
    assert {row["task_id"] for row in screen}.isdisjoint({row["task_id"] for row in primary})
    for model in LOCAL_MODELS:
        rows = [row for row in screen if row.get("model") == model]
        assert len(rows) == 4
        assert {(row.get("feedback_style"), row.get("strategy")) for row in rows} == CONDITIONS
    by_task = defaultdict(list)
    for row in screen:
        by_task[row["task_id"]].append((row["feedback_style"], row["strategy"]))
    assert all(set(values) == CONDITIONS for values in by_task.values())
    global_counts = Counter((row["feedback_style"], row["strategy"]) for row in screen)
    assert set(global_counts.values()) == {5}
    assert all(row.get("cache_hit") is False for row in primary)
    assert len({row.get("physical_call_number") for row in primary}) == len(primary)


def test_primary_factorial_counterbalances_condition_ordinal_position():
    result = run_local_campaign(
        [MockModelAdapter(model=model) for model in LOCAL_MODELS],
        run_id="final-red-team-order",
        hard_limit=480,
    )
    primary = [row for row in result["records"] if row.get("phase") == "repair_factorial"]
    grouped = defaultdict(list)
    for row in primary:
        grouped[(row["model"], row["task_id"])].append((row["feedback_style"], row["strategy"]))
    assert grouped and all(set(order) == CONDITIONS and len(order) == 4 for order in grouped.values())
    orders = list(grouped.values())
    assert len({tuple(order) for order in orders}) > 1
    for ordinal in range(4):
        counts = Counter(order[ordinal] for order in orders)
        assert set(counts) == CONDITIONS
        assert max(counts.values()) - min(counts.values()) <= 1


def test_catastrophic_lineage_is_joined_by_model_and_condition_not_list_position():
    trials = [
        {"phase": "repair_factorial", "model": "m1", "task_id": "t", "evaluation_id": "e", "feedback_style": "structured", "strategy": "targeted"},
        {"phase": "repair_factorial", "model": "m2", "task_id": "t", "evaluation_id": "e", "feedback_style": "structured", "strategy": "targeted"},
    ]
    validators = [
        {"phase": "repair_factorial", "model": "m2", "task_id": "t", "evaluation_id": "e", "stage": "repair_structured_targeted", "catastrophic": True},
        {"phase": "repair_factorial", "model": "m1", "task_id": "t", "evaluation_id": "e", "stage": "repair_structured_targeted", "catastrophic": False},
    ]
    result = {"records": trials, "validator_results": validators}
    attach_repair_validator_outcomes(result)
    by_model = {row["model"]: row["catastrophic"] for row in result["records"]}
    assert by_model == {"m1": False, "m2": True}


def test_incomplete_ollama_identity_snapshot_aborts_before_any_model_campaign(monkeypatch):
    called = {"campaign": False}

    class FakeOllama:
        provider = "ollama"
        base_url = "http://ollama.test"
        def __init__(self, model: str):
            self.model = model

    monkeypatch.setattr(local_impl, "collect_ollama_provenance", lambda *args, **kwargs: {
        "server_version": None,
        "models": {model: {"requested_name": model, "tag_name": None, "tag_digest": None, "show_payload_sha256": None} for model in LOCAL_MODELS},
    })
    def fake_campaign(*args, **kwargs):
        called["campaign"] = True
        return {"records": [], "validator_results": []}
    monkeypatch.setattr(local_impl._hardened, "run_local_campaign", fake_campaign)

    with pytest.raises(AssertionError, match="provenance|identity|digest"):
        local_impl.run_local_campaign([FakeOllama(model) for model in LOCAL_MODELS], run_id="bad-provenance", hard_limit=480)
    assert called["campaign"] is False


def test_failed_physical_call_is_recorded_as_a_failed_cell_and_is_never_cached():
    class FailingModel:
        model = "failing"
        provider = "mock"
        def complete(self, messages, *, role, context):
            record = SimpleNamespace(to_dict=lambda: {"error_class": "InjectedFailure", "model": self.model, "role": role})
            raise ModelCallError("injected failure", record)

    caller = BoundedModelCaller(PhysicalCallBudget(max_calls=2))
    model = FailingModel()
    first = caller.complete(model, [{"role": "user", "content": "x"}], role="executor", context={})
    second = caller.complete(model, [{"role": "user", "content": "x"}], role="executor", context={})
    assert first.text == second.text == ""
    assert first.cache_hit is second.cache_hit is False
    assert caller.budget.physical_calls == 2
    assert caller.budget.cache_hits == 0
    assert len(caller.calls) == 2
