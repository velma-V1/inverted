import csv
import hashlib
import json
from pathlib import Path

from inverted.assistant_value.evidence import EvidenceStore, REQUIRED_ARTIFACTS


def test_evidence_store_preserves_raw_content_and_builds_integrity_bundle(tmp_path):
    root = tmp_path / "packet"
    store = EvidenceStore(root, test_name="unit", run_id="run-1")
    prompt = [{"role": "user", "content": "verbatim prompt\nline two"}]
    response = '{"answer":"verbatim response\\nline two"}'

    store.append("tasks", {"task_id": "task-1", "seed": 7})
    store.append("prompts", {"call_id": "call-1", "messages": prompt})
    store.append("responses", {"call_id": "call-1", "response": response})
    store.append("model_calls", {"call_id": "call-1", "trial_id": "trial-1", "total_tokens": 12})
    store.append("events", {"event": "model_call", "call_id": "call-1"})

    trial = {
        "trial_id": "trial-1",
        "test_name": "unit",
        "arm": "DIRECT",
        "success": True,
        "catastrophic": False,
        "model_calls": 1,
    }
    paths = store.finalize(
        preregistration={"status": "instrument-validation"},
        config={"seed": 7},
        provenance={"python": "test"},
        metrics={"success_rate": 1.0},
        budget={"cap": 2, "used": 1, "remaining": 1, "reservations": []},
        trials=[trial],
        failures=[],
    )

    for name in REQUIRED_ARTIFACTS:
        assert (root / name).exists(), name
    assert set(paths) >= set(REQUIRED_ARTIFACTS)

    assert "verbatim prompt" in (root / "prompts.jsonl").read_text(encoding="utf-8")
    assert "verbatim response" in (root / "responses.jsonl").read_text(encoding="utf-8")
    complete = (root / "COMPLETE-EVIDENCE.txt").read_text(encoding="utf-8")
    assert "verbatim prompt" in complete
    assert "verbatim response" in complete

    integrity = json.loads((root / "integrity.json").read_text(encoding="utf-8"))
    assert integrity["status"] == "OK"
    assert integrity["budget_violation"] is False
    assert integrity["model_call_rows"] == 1

    with (root / "SHA256SUMS.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        path = root / row["path"]
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_empty_specialized_ledgers_are_still_created(tmp_path):
    root = tmp_path / "empty-packet"
    store = EvidenceStore(root, test_name="unit", run_id="run-empty")
    store.finalize(
        preregistration={},
        config={},
        provenance={},
        metrics={},
        budget={"cap": 1, "used": 0, "remaining": 1, "reservations": []},
        trials=[],
        failures=[],
    )
    for ledger in (
        "tasks.jsonl",
        "state_snapshots.jsonl",
        "model_calls.jsonl",
        "prompts.jsonl",
        "responses.jsonl",
        "actions.jsonl",
        "tool_results.jsonl",
        "oracle_results.jsonl",
        "transitions.jsonl",
        "events.jsonl",
        "anomalies.jsonl",
    ):
        assert (root / ledger).exists()
