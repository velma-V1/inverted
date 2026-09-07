"""Durable append-only storage for the canonical replay registry."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .core import (
    FailureFixture,
    ReplayRecord,
    ReplayRecordType,
    ReplayRequest,
    ReplayResult,
    from_payload,
    to_payload,
)


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class SupersessionRecord:
    old_record_id: str
    replacement_record_id: str
    reason: str
    record_id: str | None = None
    record_type: ReplayRecordType = ReplayRecordType.SUPERSESSION

    def __post_init__(self) -> None:
        for name in ("old_record_id", "replacement_record_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if self.old_record_id == self.replacement_record_id:
            raise ValueError("supersession records must link distinct records")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason is required")


@dataclass(frozen=True)
class ReplayValidation:
    ok: bool
    row_count: int
    unique_record_count: int
    missing_assets: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    broken_lineage: tuple[str, ...]
    duplicate_record_ids: tuple[str, ...]


class ReplayStore:
    """Own the single JSONL source of truth and its content-addressed assets."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.registry_path = self.root / "TEST_REPLAY.jsonl"
        self.manifest_path = self.root / "TEST_REPLAY.sha256"
        self.asset_root = self.root / "replay-assets" / "sha256"
        self._lock = threading.RLock()

    def put_asset(self, payload: Any) -> str:
        encoded = _canonical(payload)
        digest = hashlib.sha256(encoded).hexdigest()
        path = self.asset_root / f"{digest}.json"
        with self._lock:
            if path.exists():
                if path.read_bytes() != encoded:
                    raise ValueError(f"existing replay asset is corrupt: {digest}")
                return digest
            self.asset_root.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        return digest

    def read_asset(self, sha256: str) -> Any:
        path = self.asset_root / f"{sha256}.json"
        encoded = path.read_bytes()
        actual = hashlib.sha256(encoded).hexdigest()
        if actual != sha256:
            raise ValueError(f"replay asset hash mismatch: {sha256}")
        return json.loads(encoded)

    @staticmethod
    def _payload(record: ReplayRecord | SupersessionRecord) -> dict[str, Any]:
        if isinstance(record, SupersessionRecord):
            payload: dict[str, Any] = {
                "record_type": record.record_type.value,
                "old_record_id": record.old_record_id,
                "replacement_record_id": record.replacement_record_id,
                "reason": record.reason,
            }
            if record.record_id is not None:
                payload["record_id"] = record.record_id
            return payload
        return to_payload(record)

    def append(self, record: ReplayRecord | SupersessionRecord) -> str:
        payload = self._payload(record)
        supplied_id = payload.pop("record_id", None)
        record_id = hashlib.sha256(_canonical(payload)).hexdigest()
        if supplied_id is not None and supplied_id != record_id:
            raise ValueError("record_id does not match canonical record payload")
        committed = {**payload, "record_id": record_id}
        line = _canonical(committed) + b"\n"
        with self._lock:
            rows = self._raw_rows()
            for existing in rows:
                if existing.get("record_id") == record_id:
                    if existing != committed:
                        raise ValueError(f"record_id collision: {record_id}")
                    return record_id
            self.root.mkdir(parents=True, exist_ok=True)
            with self.registry_path.open("ab") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            self._write_manifest()
        return record_id

    def _write_manifest(self) -> None:
        digest = hashlib.sha256(self.registry_path.read_bytes()).hexdigest()
        temporary = self.manifest_path.with_suffix(".sha256.tmp")
        with temporary.open("wb") as handle:
            handle.write((digest + "\n").encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.manifest_path)

    def _raw_rows(self) -> list[dict[str, Any]]:
        if not self.registry_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.registry_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("registry rows must be JSON objects")
                    rows.append(value)
        return rows

    def records(self) -> tuple[ReplayRecord | SupersessionRecord, ...]:
        parsed: list[ReplayRecord | SupersessionRecord] = []
        for row in self._raw_rows():
            if row.get("record_type") == ReplayRecordType.SUPERSESSION.value:
                raw = dict(row)
                raw.pop("record_type")
                parsed.append(SupersessionRecord(**raw))
            else:
                parsed.append(from_payload(row))
        return tuple(parsed)

    def get_failure(self, failure_snapshot_id: str) -> FailureFixture:
        matches = [
            record for record in self.records()
            if isinstance(record, FailureFixture) and record.failure_snapshot_id == failure_snapshot_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one failure fixture {failure_snapshot_id!r}, found {len(matches)}")
        return matches[0]

    def supersede(self, old_record_id: str, replacement_record_id: str, reason: str) -> str:
        return self.append(SupersessionRecord(old_record_id, replacement_record_id, reason))

    def validate(self) -> ReplayValidation:
        missing_assets: set[str] = set()
        hash_mismatches: set[str] = set()
        broken: list[str] = []
        duplicate_ids: set[str] = set()
        rows: list[dict[str, Any]] = []

        registry_bytes = self.registry_path.read_bytes() if self.registry_path.exists() else b""
        expected_manifest = hashlib.sha256(registry_bytes).hexdigest()
        try:
            if self.manifest_path.read_text(encoding="ascii").strip() != expected_manifest:
                hash_mismatches.add("TEST_REPLAY.sha256")
        except FileNotFoundError:
            hash_mismatches.add("TEST_REPLAY.sha256")

        try:
            rows = self._raw_rows()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            broken.append(f"registry parse error: {exc}")

        seen: set[str] = set()
        parsed: list[ReplayRecord | SupersessionRecord] = []
        for number, row in enumerate(rows, 1):
            record_id = row.get("record_id")
            if not isinstance(record_id, str):
                broken.append(f"row {number}: missing record_id")
                continue
            if record_id in seen:
                duplicate_ids.add(record_id)
            seen.add(record_id)
            unhashed = dict(row)
            unhashed.pop("record_id", None)
            if hashlib.sha256(_canonical(unhashed)).hexdigest() != record_id:
                hash_mismatches.add(record_id)
            try:
                if row.get("record_type") == ReplayRecordType.SUPERSESSION.value:
                    raw = dict(row); raw.pop("record_type")
                    parsed.append(SupersessionRecord(**raw))
                else:
                    parsed.append(from_payload(row))
            except (TypeError, ValueError) as exc:
                broken.append(f"row {number}: invalid record: {exc}")

        for record in parsed:
            for digest in self._asset_hashes(record):
                path = self.asset_root / f"{digest}.json"
                if not path.exists():
                    missing_assets.add(digest)
                elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    hash_mismatches.add(digest)

        failure_groups: dict[str, list[FailureFixture]] = {}
        request_groups: dict[str, list[ReplayRequest]] = {}
        for item in parsed:
            if isinstance(item, FailureFixture):
                failure_groups.setdefault(item.failure_snapshot_id, []).append(item)
            elif isinstance(item, ReplayRequest):
                request_groups.setdefault(item.replay_request_id, []).append(item)
        for identity, group in failure_groups.items():
            if len(group) != 1:
                broken.append(f"failure identity {identity}: expected exactly one record, found {len(group)}")
        for identity, group in request_groups.items():
            if len(group) != 1:
                broken.append(f"request identity {identity}: expected exactly one record, found {len(group)}")
        failures = {identity: group[0] for identity, group in failure_groups.items() if len(group) == 1}
        requests = {identity: group[0] for identity, group in request_groups.items() if len(group) == 1}

        def root_failure_id(failure: FailureFixture) -> str | None:
            current = failure
            visited: set[str] = set()
            while current.parent_failure_snapshot_id is not None:
                if current.failure_snapshot_id in visited:
                    return None
                visited.add(current.failure_snapshot_id)
                parent = failures.get(current.parent_failure_snapshot_id)
                if parent is None:
                    return None
                current = parent
            return current.failure_snapshot_id

        def validate_declared_root(
            kind: str, identity: str, root_id: str, parent: FailureFixture | None
        ) -> None:
            root = failures.get(root_id)
            if root is None:
                broken.append(f"{kind} {identity}: missing root failure {root_id}")
            elif root.parent_failure_snapshot_id is not None:
                broken.append(f"{kind} {identity}: failure_snapshot_id does not identify a root failure")
            if parent is not None and root_failure_id(parent) != root_id:
                broken.append(f"{kind} {identity}: root family mismatch")

        for record in parsed:
            if isinstance(record, FailureFixture) and record.parent_failure_snapshot_id is not None:
                parent = failures.get(record.parent_failure_snapshot_id)
                if parent is None:
                    broken.append(f"failure {record.failure_snapshot_id}: missing parent {record.parent_failure_snapshot_id}")
                elif record.parent_state_hash != parent.state_hash:
                    broken.append(f"failure {record.failure_snapshot_id}: parent state mismatch")
                if root_failure_id(record) is None:
                    broken.append(f"failure {record.failure_snapshot_id}: does not resolve to a root failure")
            elif isinstance(record, ReplayRequest):
                parent = failures.get(record.parent_failure_snapshot_id)
                validate_declared_root(
                    "request", record.replay_request_id, record.failure_snapshot_id, parent
                )
                if parent is None:
                    broken.append(f"request {record.replay_request_id}: missing parent failure")
                else:
                    if record.parent_state_hash != parent.state_hash:
                        broken.append(f"request {record.replay_request_id}: parent state mismatch")
                    if record.partition != parent.partition:
                        broken.append(f"request {record.replay_request_id}: partition mismatch")
                    if (record.source_model_id, record.source_model_digest) != (parent.source_model_id, parent.source_model_digest):
                        broken.append(f"request {record.replay_request_id}: source identity mismatch")
            elif isinstance(record, ReplayResult):
                request = requests.get(record.replay_request_id)
                parent = failures.get(record.parent_failure_snapshot_id)
                validate_declared_root(
                    "result", record.replay_result_id, record.failure_snapshot_id, parent
                )
                if request is None:
                    broken.append(f"result {record.replay_result_id}: missing replay request")
                    continue
                checks = (
                    (record.failure_snapshot_id == request.failure_snapshot_id, "root identity"),
                    (record.parent_failure_snapshot_id == request.parent_failure_snapshot_id, "parent identity"),
                    (record.parent_state_hash == request.parent_state_hash, "parent state"),
                    (record.mode == request.mode, "mode"),
                    ((record.target_model_id, record.target_model_digest) == (request.target_model_id, request.target_model_digest), "target model"),
                    (record.partition == request.partition, "partition"),
                )
                for valid, label in checks:
                    if not valid:
                        broken.append(f"result {record.replay_result_id}: {label} mismatch")
                if record.child_failure_snapshot_id is not None:
                    child = failures.get(record.child_failure_snapshot_id)
                    if child is None:
                        broken.append(f"result {record.replay_result_id}: missing child failure")
                    elif (child.failure_snapshot_id == record.parent_failure_snapshot_id or
                          child.failure_snapshot_id == record.failure_snapshot_id or
                          child.parent_failure_snapshot_id != record.parent_failure_snapshot_id or
                          child.parent_state_hash != record.parent_state_hash or
                          root_failure_id(child) != record.failure_snapshot_id or
                          child.partition != record.partition or
                          (child.source_model_id, child.source_model_digest) !=
                          (record.target_model_id, record.target_model_digest)):
                        broken.append(f"result {record.replay_result_id}: incorrect child parent/state lineage")
            elif isinstance(record, SupersessionRecord):
                if record.old_record_id not in seen:
                    broken.append(f"supersession {record.record_id}: missing old record")
                if record.replacement_record_id not in seen:
                    broken.append(f"supersession {record.record_id}: missing replacement record")

        return ReplayValidation(
            ok=not (missing_assets or hash_mismatches or broken or duplicate_ids),
            row_count=len(rows), unique_record_count=len(seen),
            missing_assets=tuple(sorted(missing_assets)), hash_mismatches=tuple(sorted(hash_mismatches)),
            broken_lineage=tuple(broken), duplicate_record_ids=tuple(sorted(duplicate_ids)),
        )

    @staticmethod
    def _asset_hashes(record: ReplayRecord | SupersessionRecord) -> tuple[str, ...]:
        if isinstance(record, FailureFixture):
            return (record.model_visible_asset_sha256,)
        if isinstance(record, ReplayResult):
            return (record.output_asset_sha256, record.raw_call_asset_sha256)
        return ()
