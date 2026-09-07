from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .core import Observation


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _append_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(_canonical(payload) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class EvidenceStore:
    def __init__(self, root: str | Path, manifest: dict[str, Any]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "protocol-v2-manifest.json"
        self.observations_path = self.root / "atomic_observations.jsonl"
        self.raw_path = self.root / "raw_calls.jsonl"
        self.manifest = dict(manifest)
        self.manifest_hash = sha256_payload(self.manifest)
        self._validate_or_write_manifest()

    def _validate_or_write_manifest(self) -> None:
        if self.manifest_path.exists():
            stored = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if stored.get("manifest_sha256") != self.manifest_hash or stored.get("manifest") != self.manifest:
                raise ValueError("protocol manifest mismatch")
            return
        document = {"manifest": self.manifest, "manifest_sha256": self.manifest_hash}
        self.manifest_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def raw_rows(self) -> tuple[dict[str, Any], ...]:
        if not self.raw_path.exists():
            return ()
        return tuple(
            json.loads(line) for line in self.raw_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )


    def observation_rows(self) -> tuple[dict[str, Any], ...]:
        if not self.observations_path.exists():
            return ()
        return tuple(
            json.loads(line) for line in self.observations_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )

    def completed_trial_ids(self) -> set[str]:
        return {row["trial_id"] for row in self.observation_rows()}

    def physical_calls_used(self) -> int:
        return sum(int(row.get("physical_calls", 0)) for row in self.raw_rows())

    def commit_trial(
        self, *, trial_id: str, raw_calls: Iterable[dict[str, Any]],
        responses: Iterable[str], physical_calls: int,
        observations: Iterable[Observation],
    ) -> None:
        if trial_id in self.completed_trial_ids():
            return
        raw_payload = {
            "trial_id": trial_id,
            "physical_calls": int(physical_calls),
            "responses": list(responses),
            "raw_calls": list(raw_calls),
        }
        _append_json(self.raw_path, raw_payload)
        for observation in observations:
            row = asdict(observation)
            row["trial_id"] = trial_id
            row["profile"] = asdict(observation.profile)
            row["failure_classes"] = [item.value for item in observation.failure_classes]
            _append_json(self.observations_path, row)
