"""Durable append-only storage for the canonical replay registry."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

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


_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


def _digest(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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
        self.lock_path = self.root / ".TEST_REPLAY.lock"
        lock_key = str(self.root.resolve())
        with _LOCKS_GUARD:
            self._lock = _PROCESS_LOCKS.setdefault(lock_key, threading.RLock())

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
        """Persist directory entries where the platform exposes directory handles."""
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def put_asset(self, payload: Any) -> str:
        encoded = _canonical(payload)
        digest = hashlib.sha256(encoded).hexdigest()
        path = self.asset_root / f"{digest}.json"
        with self._transaction_lock():
            if path.exists():
                if path.read_bytes() != encoded:
                    raise ValueError(f"existing replay asset is corrupt: {digest}")
                return digest
            self.asset_root.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self._fsync_directory(self.asset_root)
        return digest

    def read_asset(self, sha256: str) -> Any:
        if not _digest(sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        with self._transaction_lock():
            path = self.asset_root / f"{sha256}.json"
            encoded = path.read_bytes()
            actual = hashlib.sha256(encoded).hexdigest()
            if actual != sha256:
                raise ValueError(f"replay asset hash mismatch: {sha256}")
            try:
                payload = json.loads(encoded)
                canonical = _canonical(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"replay asset is not canonical JSON: {sha256}") from exc
            if encoded != canonical:
                raise ValueError(f"replay asset is not canonical JSON: {sha256}")
            return payload

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
        with self._transaction_lock():
            registry_bytes = self.registry_path.read_bytes() if self.registry_path.exists() else b""
            rows = self._raw_rows()
            try:
                manifest_bytes = self.manifest_path.read_bytes()
            except FileNotFoundError:
                manifest_bytes = None
            except OSError as exc:
                raise ValueError("registry manifest mismatch; refusing append") from exc
            full_manifest = (
                hashlib.sha256(registry_bytes).hexdigest().encode("ascii") + b"\n"
            )
            matches = [
                (index, existing)
                for index, existing in enumerate(rows)
                if existing.get("record_id") == record_id
            ]
            if matches:
                if any(existing != committed for _, existing in matches):
                    raise ValueError(f"record_id collision: {record_id}")
                if manifest_bytes == full_manifest:
                    return record_id
                final_index = len(rows) - 1
                if len(matches) == 1 and matches[0][0] == final_index:
                    prefix = registry_bytes[:-len(line)]
                    prefix_manifest = hashlib.sha256(prefix).hexdigest().encode("ascii") + b"\n"
                    if manifest_bytes == prefix_manifest or (not prefix and manifest_bytes is None):
                        self._write_manifest()
                        return record_id
                raise ValueError("registry manifest mismatch; refusing unsafe repair")
            if manifest_bytes != full_manifest and not (not registry_bytes and manifest_bytes is None):
                raise ValueError("registry manifest mismatch; refusing append")
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
        self._fsync_directory(self.root)

    def _raw_rows(self) -> list[dict[str, Any]]:
        if not self.registry_path.exists():
            return []
        encoded = self.registry_path.read_bytes()
        if encoded and not encoded.endswith(b"\n"):
            raise ValueError("registry must be newline-delimited with a final newline")
        rows: list[dict[str, Any]] = []
        for number, line in enumerate(encoded.splitlines(keepends=True), 1):
            body = line[:-1]
            if not body.strip():
                raise ValueError(f"registry row {number} is blank")
            value = json.loads(body.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("registry rows must be JSON objects")
            if line != _canonical(value) + b"\n":
                raise ValueError(f"registry row {number} is not canonical compact sorted UTF-8 JSON")
            rows.append(value)
        return rows

    def _records_unlocked(self) -> tuple[ReplayRecord | SupersessionRecord, ...]:
        parsed: list[ReplayRecord | SupersessionRecord] = []
        for row in self._raw_rows():
            if row.get("record_type") == ReplayRecordType.SUPERSESSION.value:
                raw = dict(row)
                raw.pop("record_type")
                parsed.append(SupersessionRecord(**raw))
            else:
                parsed.append(from_payload(row))
        return tuple(parsed)

    def records(self) -> tuple[ReplayRecord | SupersessionRecord, ...]:
        with self._transaction_lock():
            return self._records_unlocked()

    def get_failure(self, failure_snapshot_id: str) -> FailureFixture:
        with self._transaction_lock():
            records = self._records_unlocked()
            matches = [
                record for record in records
                if isinstance(record, FailureFixture)
                and record.failure_snapshot_id == failure_snapshot_id
            ]
            if not matches:
                raise KeyError(f"failure fixture {failure_snapshot_id!r} not found")
            if len(matches) == 1:
                return matches[0]
            ids = {record.record_id for record in matches}
            links = {
                record.old_record_id: record.replacement_record_id
                for record in records
                if isinstance(record, SupersessionRecord)
                and record.old_record_id in ids and record.replacement_record_id in ids
            }
            active = [record for record in matches if record.record_id not in links]
            incoming = {replacement for replacement in links.values()}
            starts = [record for record in matches if record.record_id not in incoming]
            if len(links) != len(matches) - 1 or len(active) != 1 or len(starts) != 1:
                raise KeyError(f"failure fixture {failure_snapshot_id!r} has invalid supersession chain")
            visited: set[str | None] = set()
            current = starts[0].record_id
            while current in links and current not in visited:
                visited.add(current)
                current = links[current]
            if current != active[0].record_id or len(visited) != len(matches) - 1:
                raise KeyError(f"failure fixture {failure_snapshot_id!r} has invalid supersession chain")
            return active[0]

    def supersede(self, old_record_id: str, replacement_record_id: str, reason: str) -> str:
        return self.append(SupersessionRecord(old_record_id, replacement_record_id, reason))

    def validate(self) -> ReplayValidation:
        with self._transaction_lock():
            return self._validate_unlocked()

    def _validate_unlocked(self) -> ReplayValidation:
        missing_assets: set[str] = set()
        hash_mismatches: set[str] = set()
        broken: list[str] = []
        duplicate_ids: set[str] = set()
        rows: list[dict[str, Any]] = []

        try:
            registry_bytes = self.registry_path.read_bytes() if self.registry_path.exists() else b""
        except OSError as exc:
            broken.append(f"registry read error: {exc}")
            registry_bytes = None

        if registry_bytes is not None:
            expected_manifest = hashlib.sha256(registry_bytes).hexdigest()
            try:
                expected_manifest_bytes = expected_manifest.encode("ascii") + b"\n"
                if self.manifest_path.read_bytes() != expected_manifest_bytes:
                    hash_mismatches.add("TEST_REPLAY.sha256")
            except OSError:
                hash_mismatches.add("TEST_REPLAY.sha256")

            try:
                rows = self._raw_rows()
            except OSError as exc:
                broken.append(f"registry read error: {exc}")
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
                try:
                    if not path.exists():
                        missing_assets.add(digest)
                        continue
                    encoded = path.read_bytes()
                except OSError:
                    hash_mismatches.add(digest)
                    continue
                if hashlib.sha256(encoded).hexdigest() != digest:
                    hash_mismatches.add(digest)
                    continue
                try:
                    asset_payload = json.loads(encoded)
                    if encoded != _canonical(asset_payload):
                        hash_mismatches.add(digest)
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                    hash_mismatches.add(digest)

        records_by_id = {
            record.record_id: record for record in parsed if record.record_id is not None
        }

        def logical_key(record: ReplayRecord | SupersessionRecord) -> tuple[type[Any], str] | None:
            if isinstance(record, FailureFixture):
                return (FailureFixture, record.failure_snapshot_id)
            if isinstance(record, ReplayRequest):
                return (ReplayRequest, record.replay_request_id)
            if isinstance(record, ReplayResult):
                return (ReplayResult, record.replay_result_id)
            return None

        valid_edges: dict[str, str] = {}
        incoming: dict[str, str] = {}
        all_edges: dict[str, list[str]] = {}
        for record in parsed:
            if not isinstance(record, SupersessionRecord):
                continue
            old = records_by_id.get(record.old_record_id)
            replacement = records_by_id.get(record.replacement_record_id)
            if old is None:
                broken.append(f"supersession {record.record_id}: missing old record")
            if replacement is None:
                broken.append(f"supersession {record.record_id}: missing replacement record")
            if old is None or replacement is None:
                continue
            all_edges.setdefault(record.old_record_id, []).append(record.replacement_record_id)
            old_key = logical_key(old)
            replacement_key = logical_key(replacement)
            if old_key is None or replacement_key is None or type(old) is not type(replacement):
                broken.append(f"supersession {record.record_id}: incompatible record type")
                continue
            if old_key != replacement_key:
                broken.append(f"supersession {record.record_id}: incompatible logical identity")
                continue
            if record.old_record_id in valid_edges:
                broken.append(f"supersession {record.record_id}: multiple replacements for one record")
                continue
            if record.replacement_record_id in incoming:
                broken.append(f"supersession {record.record_id}: replacement has multiple predecessors")
                continue
            valid_edges[record.old_record_id] = record.replacement_record_id
            incoming[record.replacement_record_id] = record.old_record_id

        visiting: set[str] = set()
        visited: set[str] = set()

        def has_cycle(record_id: str) -> bool:
            if record_id in visiting:
                return True
            if record_id in visited:
                return False
            visiting.add(record_id)
            for replacement_id in all_edges.get(record_id, ()):
                if has_cycle(replacement_id):
                    return True
            visiting.remove(record_id)
            visited.add(record_id)
            return False

        if any(has_cycle(record_id) for record_id in tuple(all_edges)):
            broken.append("supersession cycle detected")

        groups: dict[tuple[type[Any], str], list[ReplayRecord]] = {}
        for record in parsed:
            key = logical_key(record)
            if key is not None:
                groups.setdefault(key, []).append(record)

        labels = {FailureFixture: "failure", ReplayRequest: "request", ReplayResult: "result"}
        active_records: list[ReplayRecord] = []
        for (record_type, identity), group in groups.items():
            if len(group) == 1:
                active_records.append(group[0])
                continue
            group_ids = {record.record_id for record in group}
            starts = [record for record in group if record.record_id not in incoming]
            ends = [record for record in group if record.record_id not in valid_edges]
            edge_count = sum(
                1 for old_id, replacement_id in valid_edges.items()
                if old_id in group_ids and replacement_id in group_ids
            )
            chain_valid = len(starts) == 1 and len(ends) == 1 and edge_count == len(group) - 1
            if chain_valid:
                traversed: set[str | None] = set()
                current = starts[0].record_id
                while current in valid_edges and current not in traversed:
                    traversed.add(current)
                    current = valid_edges[current]
                chain_valid = current == ends[0].record_id and len(traversed) == len(group) - 1
            if not chain_valid:
                broken.append(
                    f"{labels[record_type]} identity {identity}: records must form a single acyclic supersession chain"
                )
            else:
                active_records.append(ends[0])

        failures = {
            record.failure_snapshot_id: record
            for record in active_records if isinstance(record, FailureFixture)
        }
        requests = {
            record.replay_request_id: record
            for record in active_records if isinstance(record, ReplayRequest)
        }

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

        child_claims: dict[str, list[str]] = {}
        for record in active_records:
            if isinstance(record, FailureFixture) and record.parent_failure_snapshot_id is not None:
                parent = failures.get(record.parent_failure_snapshot_id)
                if parent is None:
                    broken.append(f"failure {record.failure_snapshot_id}: missing parent {record.parent_failure_snapshot_id}")
                else:
                    if record.parent_state_hash != parent.state_hash:
                        broken.append(f"failure {record.failure_snapshot_id}: parent state mismatch")
                    if record.family != parent.family:
                        broken.append(
                            f"failure {record.failure_snapshot_id}: family mismatch with parent "
                            f"{parent.failure_snapshot_id}"
                        )
                root_id = root_failure_id(record)
                if root_id is None:
                    broken.append(f"failure {record.failure_snapshot_id}: does not resolve to a root failure")
                elif record.family != failures[root_id].family:
                    broken.append(f"failure {record.failure_snapshot_id}: family mismatch with root {root_id}")
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
                    child_claims.setdefault(record.child_failure_snapshot_id, []).append(record.replay_result_id)
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
        for failure in failures.values():
            if failure.parent_failure_snapshot_id is None:
                continue
            claims = child_claims.get(failure.failure_snapshot_id, [])
            if not claims:
                broken.append(
                    f"failure {failure.failure_snapshot_id}: non-root child is not claimed by a replay result"
                )
            elif len(claims) > 1:
                broken.append(
                    f"failure {failure.failure_snapshot_id}: child is claimed by multiple replay results"
                )

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
