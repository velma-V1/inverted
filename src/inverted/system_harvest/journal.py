from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class JournalIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class JournalRecord:
    sequence: int
    campaign_id: str
    kind: str
    payload: Any
    record_sha256: str


def _hash_record(sequence: int, campaign_id: str, kind: str, payload: Any) -> str:
    body = {"sequence": sequence, "campaign_id": campaign_id, "kind": kind, "payload": payload}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class HarvestJournal:
    def __init__(self, path: str | Path, campaign_id: str):
        self.path = Path(path)
        self.campaign_id = campaign_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records = self._load_and_verify()
    def _load_and_verify(self) -> list[JournalRecord]:
        if not self.path.exists():
            return []
        records: list[JournalRecord] = []
        for expected_sequence, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalIntegrityError("journal contains invalid JSON") from exc
            if row.get("campaign_id") != self.campaign_id:
                raise JournalIntegrityError("journal campaign identity mismatch")
            if row.get("sequence") != expected_sequence:
                raise JournalIntegrityError("journal sequence mismatch")
            digest = _hash_record(expected_sequence, self.campaign_id, row.get("kind"), row.get("payload"))
            if row.get("record_sha256") != digest:
                raise JournalIntegrityError("journal record hash mismatch")
            records.append(JournalRecord(expected_sequence, self.campaign_id, row["kind"], row["payload"], digest))
        return records

    def append(self, kind: str, payload: Any) -> JournalRecord:
        sequence = len(self._records) + 1
        digest = _hash_record(sequence, self.campaign_id, kind, payload)
        record = JournalRecord(sequence, self.campaign_id, kind, payload, digest)
        row = {"sequence": sequence, "campaign_id": self.campaign_id, "kind": kind,
               "payload": payload, "record_sha256": digest}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._records.append(record)
        return record

    def read_all(self) -> tuple[JournalRecord, ...]:
        return tuple(self._load_and_verify())
