import json

import pytest

from inverted.system_harvest.journal import HarvestJournal, JournalIntegrityError


def test_journal_survives_reopen_and_preserves_campaign_identity(tmp_path):
    path = tmp_path / "journal.jsonl"
    journal = HarvestJournal(path, "SYSTEM_HARVEST_11")
    first = journal.append("ATTEMPT_STATE", {"attempt_id": "C:S:E:A1", "state": "RUNNING"})
    reopened = HarvestJournal(path, "SYSTEM_HARVEST_11")
    second = reopened.append("ATTEMPT_STATE", {"attempt_id": "C:S:E:A1", "state": "RESUME"})
    assert first.sequence == 1
    assert second.sequence == 2
    assert [r.payload["state"] for r in reopened.read_all()] == ["RUNNING", "RESUME"]


def test_journal_rejects_different_campaign_id(tmp_path):
    path = tmp_path / "journal.jsonl"
    HarvestJournal(path, "A").append("X", {"v": 1})
    with pytest.raises(JournalIntegrityError, match="campaign"):
        HarvestJournal(path, "B")


def test_journal_detects_tampering(tmp_path):
    path = tmp_path / "journal.jsonl"
    HarvestJournal(path, "C").append("X", {"v": 1})
    row = json.loads(path.read_text(encoding="utf-8"))
    row["payload"]["v"] = 2
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(JournalIntegrityError, match="hash"):
        HarvestJournal(path, "C")
