from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .contracts import MechanismCandidate

VALID_STATUSES = {"proposed", "causally_supported", "dev_passed", "retained", "rejected", "bounded"}


class MechanismRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.records: dict[str, dict] = {}
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = {x["candidate_id"]: x for x in payload}

    def put(self, candidate: MechanismCandidate) -> None:
        if candidate.status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {candidate.status}")
        self.records[candidate.candidate_id] = asdict(candidate)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(list(self.records.values()), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def get(self, candidate_id: str) -> dict | None:
        return self.records.get(candidate_id)
