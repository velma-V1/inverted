"""Integrity-gated storage for V3 causal hypotheses and interventions."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    HypothesisStatus,
    InterventionDefinition,
    InterventionKind,
)
from .replay_store import ReplayStore


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported causal JSON value: {type(value).__name__}")


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _hypothesis_payload(value: CausalHypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": value.hypothesis_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "parent_state_hash": value.parent_state_hash,
        "divergence": {
            "divergence_class": value.divergence.divergence_class.value,
            "observable_path": value.divergence.observable_path,
            "event_index": value.divergence.event_index,
            "evidence_refs": value.divergence.evidence_refs,
            "confidence": value.divergence.confidence,
        },
        "owner_candidate": value.owner_candidate.value,
        "claim": value.claim,
        "expected_if_true": value.expected_if_true,
        "falsifier": value.falsifier,
        "status": value.status.value,
        "protected_exploration": value.protected_exploration,
    }


def _hypothesis_from_payload(payload: Mapping[str, Any]) -> CausalHypothesis:
    raw = dict(payload)
    divergence_raw = dict(raw["divergence"])
    return CausalHypothesis(
        hypothesis_id=raw["hypothesis_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        parent_state_hash=raw["parent_state_hash"],
        divergence=FirstDivergence(
            divergence_class=DivergenceClass(divergence_raw["divergence_class"]),
            observable_path=divergence_raw["observable_path"],
            event_index=divergence_raw["event_index"],
            evidence_refs=tuple(divergence_raw["evidence_refs"]),
            confidence=divergence_raw["confidence"],
        ),
        owner_candidate=ArchitectureOwner(raw["owner_candidate"]),
        claim=raw["claim"],
        expected_if_true=raw["expected_if_true"],
        falsifier=raw["falsifier"],
        status=HypothesisStatus(raw.get("status", HypothesisStatus.ACTIVE.value)),
        protected_exploration=bool(raw.get("protected_exploration", False)),
    )


def _intervention_payload(value: InterventionDefinition) -> dict[str, Any]:
    return {
        "intervention_id": value.intervention_id,
        "hypothesis_id": value.hypothesis_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "parent_state_hash": value.parent_state_hash,
        "kind": value.kind.value,
        "label": value.label,
        "changed_dimensions": value.changed_dimensions,
        "overrides": value.overrides,
        "expected_causal_implication": value.expected_causal_implication,
        "projected_physical_calls": value.projected_physical_calls,
        "composition": value.composition,
        "sham_for": value.sham_for,
        "ablates": value.ablates,
        "protected_exploration": value.protected_exploration,
    }


def _intervention_from_payload(payload: Mapping[str, Any]) -> InterventionDefinition:
    raw = dict(payload)
    return InterventionDefinition(
        intervention_id=raw["intervention_id"],
        hypothesis_id=raw["hypothesis_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        parent_state_hash=raw["parent_state_hash"],
        kind=InterventionKind(raw["kind"]),
        label=raw["label"],
        changed_dimensions=tuple(raw.get("changed_dimensions", ())),
        overrides=dict(raw.get("overrides", {})),
        expected_causal_implication=raw["expected_causal_implication"],
        projected_physical_calls=raw.get("projected_physical_calls", 1),
        composition=tuple(raw.get("composition", ())),
        sham_for=raw.get("sham_for"),
        ablates=tuple(raw.get("ablates", ())),
        protected_exploration=bool(raw.get("protected_exploration", False)),
    )


_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


@dataclass(frozen=True)
class CausalStoreValidation:
    ok: bool
    hypothesis_count: int
    intervention_count: int
    missing_assets: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    broken_lineage: tuple[str, ...]
    duplicate_hypothesis_ids: tuple[str, ...]


class CausalEvidenceStore:
    """Persist causal metadata without creating a competing replay store."""

    def __init__(self, root: Path, *, replay_store: ReplayStore | None = None) -> None:
        self.root = Path(root)
        self.replay_store = replay_store
        self.hypothesis_path = self.root / "causal-hypotheses.jsonl"
        self.hypothesis_manifest_path = self.root / "causal-hypotheses.sha256"
        self.intervention_registry_path = self.root / "intervention-registry.json"
        self.intervention_manifest_path = self.root / "intervention-registry.sha256"
        self.asset_root = self.root / "causal-assets" / "sha256"
        self.lock_path = self.root / ".causal-evidence.lock"
        with _LOCKS_GUARD:
            self._lock = _PROCESS_LOCKS.setdefault(str(self.root.resolve()), threading.RLock())

    @contextmanager
    def _transaction_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.lock_path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    handle.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _write_atomic(self, path: Path, encoded: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        self._fsync_directory(path.parent)

    def _write_manifest(self, source: Path, manifest: Path) -> None:
        encoded = source.read_bytes() if source.exists() else b""
        digest = hashlib.sha256(encoded).hexdigest().encode("ascii") + b"\n"
        self._write_atomic(manifest, digest)

    def _require_failure(self, failure_snapshot_id: str, parent_state_hash: str) -> None:
        if self.replay_store is None:
            return
        try:
            fixture = self.replay_store.get_failure(failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("causal record references an unknown replay failure") from exc
        if fixture.state_hash != parent_state_hash:
            raise ValueError("causal record parent state hash does not match replay fixture")

    def append_hypothesis(self, hypothesis: CausalHypothesis) -> str:
        if not isinstance(hypothesis, CausalHypothesis):
            raise TypeError("hypothesis must be CausalHypothesis")
        self._require_failure(hypothesis.failure_snapshot_id, hypothesis.parent_state_hash)
        line = _canonical(_hypothesis_payload(hypothesis)) + b"\n"
        with self._transaction_lock():
            rows = self._hypothesis_rows_unlocked()
            matches = [row for row in rows if row[0] == hypothesis.hypothesis_id]
            if matches:
                if any(existing != line[:-1] for _, existing in matches):
                    raise ValueError("existing hypothesis ID has different canonical content")
                return hypothesis.hypothesis_id
            with self.hypothesis_path.open("ab") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            self._write_manifest(self.hypothesis_path, self.hypothesis_manifest_path)
        return hypothesis.hypothesis_id

    def _hypothesis_rows_unlocked(self) -> list[tuple[str, bytes]]:
        if not self.hypothesis_path.exists():
            return []
        encoded = self.hypothesis_path.read_bytes()
        if encoded and not encoded.endswith(b"\n"):
            raise ValueError("causal hypotheses must end with a newline")
        rows: list[tuple[str, bytes]] = []
        for number, line in enumerate(encoded.splitlines(), 1):
            if not line:
                raise ValueError(f"causal hypothesis row {number} is blank")
            payload = json.loads(line)
            if line != _canonical(payload):
                raise ValueError(f"causal hypothesis row {number} is not canonical JSON")
            value = _hypothesis_from_payload(payload)
            rows.append((value.hypothesis_id, line))
        return rows

    def hypotheses(self, failure_snapshot_id: str | None = None) -> tuple[CausalHypothesis, ...]:
        with self._transaction_lock():
            if not self.hypothesis_path.exists():
                return ()
            values = tuple(
                _hypothesis_from_payload(json.loads(line))
                for line in self.hypothesis_path.read_bytes().splitlines()
                if line
            )
        if failure_snapshot_id is None:
            return values
        return tuple(value for value in values if value.failure_snapshot_id == failure_snapshot_id)

    def _registry_payload_unlocked(self) -> dict[str, Any]:
        if not self.intervention_registry_path.exists():
            return {"version": 1, "interventions": {}}
        encoded = self.intervention_registry_path.read_bytes()
        payload = json.loads(encoded)
        if encoded != _canonical(payload):
            raise ValueError("intervention registry is not canonical JSON")
        if payload.get("version") != 1 or not isinstance(payload.get("interventions"), dict):
            raise ValueError("intervention registry schema mismatch")
        return payload

    def _put_asset_unlocked(self, payload: Mapping[str, Any]) -> str:
        encoded = _canonical(payload)
        digest = hashlib.sha256(encoded).hexdigest()
        path = self.asset_root / f"{digest}.json"
        if path.exists():
            if path.read_bytes() != encoded:
                raise ValueError(f"existing causal asset is corrupt: {digest}")
            return digest
        self.asset_root.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        self._fsync_directory(self.asset_root)
        return digest

    def register_intervention(self, intervention: InterventionDefinition) -> str:
        if not isinstance(intervention, InterventionDefinition):
            raise TypeError("intervention must be InterventionDefinition")
        self._require_failure(intervention.failure_snapshot_id, intervention.parent_state_hash)
        hypotheses = {item.hypothesis_id: item for item in self.hypotheses(intervention.failure_snapshot_id)}
        hypothesis = hypotheses.get(intervention.hypothesis_id)
        if hypothesis is None:
            raise ValueError("intervention hypothesis is not registered")
        if hypothesis.parent_state_hash != intervention.parent_state_hash:
            raise ValueError("intervention parent state does not match hypothesis")
        with self._transaction_lock():
            digest = self._put_asset_unlocked(_intervention_payload(intervention))
            registry = self._registry_payload_unlocked()
            interventions = registry["interventions"]
            existing = interventions.get(intervention.intervention_id)
            entry = {"asset_sha256": digest}
            if existing is not None:
                if existing != entry:
                    raise ValueError("existing intervention ID has different asset hash")
                return digest
            interventions[intervention.intervention_id] = entry
            self._write_atomic(self.intervention_registry_path, _canonical(registry))
            self._write_manifest(self.intervention_registry_path, self.intervention_manifest_path)
        return digest

    def get_intervention(self, intervention_id: str) -> InterventionDefinition:
        with self._transaction_lock():
            registry = self._registry_payload_unlocked()
            entry = registry["interventions"].get(intervention_id)
            if entry is None:
                raise KeyError(intervention_id)
            digest = entry["asset_sha256"]
            path = self.asset_root / f"{digest}.json"
            encoded = path.read_bytes()
            if hashlib.sha256(encoded).hexdigest() != digest:
                raise ValueError("intervention asset hash mismatch")
            payload = json.loads(encoded)
            if encoded != _canonical(payload):
                raise ValueError("intervention asset is not canonical JSON")
            value = _intervention_from_payload(payload)
            if value.intervention_id != intervention_id:
                raise ValueError("intervention registry logical ID mismatch")
            return value

    def validate(self) -> CausalStoreValidation:
        missing_assets: set[str] = set()
        mismatches: set[str] = set()
        broken: list[str] = []
        duplicates: set[str] = set()
        hypothesis_values: list[CausalHypothesis] = []
        intervention_count = 0

        with self._transaction_lock():
            if self.hypothesis_path.exists():
                encoded = self.hypothesis_path.read_bytes()
                expected = hashlib.sha256(encoded).hexdigest().encode("ascii") + b"\n"
                try:
                    if self.hypothesis_manifest_path.read_bytes() != expected:
                        mismatches.add("causal-hypotheses.sha256")
                except OSError:
                    mismatches.add("causal-hypotheses.sha256")
                seen: set[str] = set()
                for number, line in enumerate(encoded.splitlines(), 1):
                    try:
                        payload = json.loads(line)
                        if line != _canonical(payload):
                            raise ValueError
                        value = _hypothesis_from_payload(payload)
                    except Exception:
                        mismatches.add(f"causal-hypotheses.jsonl:{number}")
                        continue
                    if value.hypothesis_id in seen:
                        duplicates.add(value.hypothesis_id)
                    seen.add(value.hypothesis_id)
                    hypothesis_values.append(value)
            elif self.hypothesis_manifest_path.exists():
                mismatches.add("causal-hypotheses.sha256")

            if self.intervention_registry_path.exists():
                encoded = self.intervention_registry_path.read_bytes()
                expected = hashlib.sha256(encoded).hexdigest().encode("ascii") + b"\n"
                try:
                    if self.intervention_manifest_path.read_bytes() != expected:
                        mismatches.add("intervention-registry.sha256")
                except OSError:
                    mismatches.add("intervention-registry.sha256")
            elif self.intervention_manifest_path.exists():
                mismatches.add("intervention-registry.sha256")

            try:
                registry = self._registry_payload_unlocked()
            except Exception:
                registry = {"version": 1, "interventions": {}}
                mismatches.add("intervention-registry.json")

            hypotheses_by_id = {item.hypothesis_id: item for item in hypothesis_values}
            for intervention_id, entry in registry["interventions"].items():
                intervention_count += 1
                digest = entry.get("asset_sha256") if isinstance(entry, dict) else None
                if not isinstance(digest, str) or len(digest) != 64:
                    mismatches.add(f"intervention:{intervention_id}")
                    continue
                path = self.asset_root / f"{digest}.json"
                if not path.exists():
                    missing_assets.add(digest)
                    continue
                encoded = path.read_bytes()
                if hashlib.sha256(encoded).hexdigest() != digest:
                    mismatches.add(digest)
                    continue
                try:
                    payload = json.loads(encoded)
                    if encoded != _canonical(payload):
                        raise ValueError
                    intervention = _intervention_from_payload(payload)
                except Exception:
                    mismatches.add(digest)
                    continue
                if intervention.intervention_id != intervention_id:
                    broken.append(f"intervention {intervention_id}: logical ID mismatch")
                hypothesis = hypotheses_by_id.get(intervention.hypothesis_id)
                if hypothesis is None:
                    broken.append(f"intervention {intervention_id}: missing hypothesis")
                elif (
                    hypothesis.failure_snapshot_id != intervention.failure_snapshot_id
                    or hypothesis.parent_state_hash != intervention.parent_state_hash
                ):
                    broken.append(f"intervention {intervention_id}: hypothesis lineage mismatch")

        if self.replay_store is not None:
            for hypothesis in hypothesis_values:
                try:
                    fixture = self.replay_store.get_failure(hypothesis.failure_snapshot_id)
                except KeyError:
                    broken.append(f"hypothesis {hypothesis.hypothesis_id}: missing replay failure")
                    continue
                if fixture.state_hash != hypothesis.parent_state_hash:
                    broken.append(f"hypothesis {hypothesis.hypothesis_id}: parent state mismatch")

        return CausalStoreValidation(
            ok=not (missing_assets or mismatches or broken or duplicates),
            hypothesis_count=len(hypothesis_values),
            intervention_count=intervention_count,
            missing_assets=tuple(sorted(missing_assets)),
            hash_mismatches=tuple(sorted(mismatches)),
            broken_lineage=tuple(broken),
            duplicate_hypothesis_ids=tuple(sorted(duplicates)),
        )
