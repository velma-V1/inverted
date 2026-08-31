from __future__ import annotations

from inverted.models import MockModelAdapter
from inverted.test2_cli import _local_evidence
from inverted.test2_local import LOCAL_MODELS
import inverted.test2_local_impl as local_impl
from inverted.test2_readiness import finalize_test2_evidence


def _primary_rows():
    rows = []
    for i in range(18):
        model = LOCAL_MODELS[i % 3]
        task_id = f"t{i}"
        rows.append({
            "phase": "repair_factorial", "role": "repairer", "model": model,
            "task_id": task_id, "evaluation_id": f"st-{task_id}",
            "feedback_style": "structured", "strategy": "targeted",
            "success": i < 17, "catastrophic": False,
        })
        rows.append({
            "phase": "repair_factorial", "role": "repairer", "model": model,
            "task_id": task_id, "evaluation_id": f"rr-{task_id}",
            "feedback_style": "raw", "strategy": "regenerate",
            "success": i < 6, "catastrophic": False,
        })
    return rows


def _local(records, ollama_provenance):
    return {
        "records": records,
        "raw_calls": [],
        "physical_model_calls": 0,
        "cache_hits": 0,
        "hard_call_limit": 480,
        "models": list(LOCAL_MODELS),
        "phase_limits": {},
        "candidates": [],
        "events": [],
        "validator_results": [],
        "repairs": [],
        "ollama_provenance": ollama_provenance,
    }


def test_real_campaign_wrapper_snapshots_ollama_identity_before_and_after(monkeypatch):
    class FakeOllama(MockModelAdapter):
        provider = "ollama"

        def __init__(self, model: str):
            super().__init__(model=model)
            self.base_url = "http://ollama.test"

    snapshots = []

    def fake_collect(base_url, models, **kwargs):
        snapshots.append((base_url, tuple(models)))
        return {
            "server_version": "1.0",
            "models": {model: {"tag_digest": f"digest-{model}", "show_payload_sha256": f"show-{model}"} for model in models},
        }

    monkeypatch.setattr(local_impl, "collect_ollama_provenance", fake_collect, raising=False)
    result = local_impl.run_local_campaign(
        [FakeOllama(model) for model in LOCAL_MODELS],
        run_id="provenance-wrapper",
        hard_limit=480,
    )
    assert snapshots == [
        ("http://ollama.test", tuple(LOCAL_MODELS)),
        ("http://ollama.test", tuple(LOCAL_MODELS)),
    ]
    assert result["ollama_provenance"]["identity_match"] is True


def test_local_evidence_preserves_before_after_ollama_identity_snapshot():
    snapshot = {
        "before": {"server_version": "1", "models": {LOCAL_MODELS[0]: {"tag_digest": "abc"}}},
        "after": {"server_version": "1", "models": {LOCAL_MODELS[0]: {"tag_digest": "abc"}}},
        "identity_match": True,
    }
    evidence = _local_evidence(
        _local([], snapshot),
        {},
        {"local": {"models": list(LOCAL_MODELS)}},
        "provenance-preservation",
    )
    assert evidence["provenance"]["models"] == snapshot


def test_ollama_identity_drift_forces_inconclusive_even_when_primary_statistics_support():
    drift = {
        "before": {"server_version": "1", "models": {model: {"tag_digest": f"{model}-before"} for model in LOCAL_MODELS}},
        "after": {"server_version": "1", "models": {model: {"tag_digest": f"{model}-after"} for model in LOCAL_MODELS}},
        "identity_match": False,
    }
    evidence = _local_evidence(
        _local(_primary_rows(), drift),
        {},
        {"local": {"models": list(LOCAL_MODELS)}},
        "provenance-drift",
    )
    finalize_test2_evidence(evidence)
    assert evidence["verdict"]["verdict"] == "INCONCLUSIVE"
    assert "ollama_identity_drift" in evidence["verdict"]["material_contamination_blockers"]
