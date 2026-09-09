"""Append-only Stage-8 capability-compilation metadata storage."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, TypeVar

from .compilation_core import (
    CompilationCandidate,
    CompilationDisposition,
    CompilationKind,
    CompilationPlan,
    CompiledCapability,
)
from .core import Partition
from .mutation_core import GeneralizationClass
from .replay_store import ReplayStore


T = TypeVar("T")
_RAW_KEYS = frozenset(
    {
        "raw_response",
        "raw_model_response",
        "raw_call",
        "model_output",
        "output_text",
        "prompt",
        "messages",
    }
)
_DATA_FILES = (
    "compilation-candidates.jsonl",
    "compilation-decisions.jsonl",
    "compiled-capabilities.jsonl",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported compilation-store value: {type(value).__name__}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _contains_raw_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _RAW_KEYS:
                return key
            nested = _contains_raw_key(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _contains_raw_key(item)
            if nested is not None:
                return nested
    return None


def _candidate_payload(value: CompilationCandidate) -> dict[str, Any]:
    return {
        "candidate_id": value.candidate_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "mechanism_id": value.mechanism_id,
        "generalization_profile_id": value.generalization_profile_id,
        "prior_generalized_evidence_ref": value.prior_generalized_evidence_ref,
        "generalization_class": value.generalization_class.value,
        "mechanism_label_ids": value.mechanism_label_ids,
        "evidence_refs": value.evidence_refs,
        "source_hashes": value.source_hashes,
        "supported_kinds": tuple(item.value for item in value.supported_kinds),
        "excluded_cheaper_kinds": value.excluded_cheaper_kinds,
        "trigger_contract": value.trigger_contract,
        "compiled_payload": value.compiled_payload,
        "verifier_contract": value.verifier_contract,
        "negative_transfer_boundary": value.negative_transfer_boundary,
        "tested_region": value.tested_region,
        "rollback_action": value.rollback_action,
        "partition": value.partition.value,
        "operating_surface_profile_id": value.operating_surface_profile_id,
        "tomography_assessment_id": value.tomography_assessment_id,
        "model_internal_residual": value.model_internal_residual,
        "decision_id": value.decision_id,
    }


def _candidate_from(payload: Mapping[str, Any]) -> CompilationCandidate:
    raw = dict(payload)
    return CompilationCandidate(
        candidate_id=str(raw["candidate_id"]),
        failure_snapshot_id=str(raw["failure_snapshot_id"]),
        mechanism_id=str(raw["mechanism_id"]),
        generalization_profile_id=raw.get("generalization_profile_id"),
        prior_generalized_evidence_ref=raw.get("prior_generalized_evidence_ref"),
        generalization_class=GeneralizationClass(raw["generalization_class"]),
        mechanism_label_ids=tuple(raw["mechanism_label_ids"]),
        evidence_refs=tuple(raw["evidence_refs"]),
        source_hashes=dict(raw["source_hashes"]),
        supported_kinds=tuple(CompilationKind(item) for item in raw["supported_kinds"]),
        excluded_cheaper_kinds=dict(raw["excluded_cheaper_kinds"]),
        trigger_contract=dict(raw["trigger_contract"]),
        compiled_payload=dict(raw["compiled_payload"]),
        verifier_contract=dict(raw["verifier_contract"]),
        negative_transfer_boundary=tuple(raw["negative_transfer_boundary"]),
        tested_region=str(raw["tested_region"]),
        rollback_action=str(raw["rollback_action"]),
        partition=Partition(raw["partition"]),
        operating_surface_profile_id=raw.get("operating_surface_profile_id"),
        tomography_assessment_id=raw.get("tomography_assessment_id"),
        model_internal_residual=bool(raw.get("model_internal_residual", False)),
        decision_id=str(raw.get("decision_id", "D12")),
    )


def _plan_payload(value: CompilationPlan) -> dict[str, Any]:
    return {
        "plan_id": value.plan_id,
        "candidate_id": value.candidate_id,
        "selected_kind": value.selected_kind.value,
        "rejected_cheaper_kinds": value.rejected_cheaper_kinds,
        "evidence_refs": value.evidence_refs,
        "projected_model_calls": value.projected_model_calls,
        "expected_disposition": value.expected_disposition.value,
    }


def _plan_from(payload: Mapping[str, Any]) -> CompilationPlan:
    raw = dict(payload)
    return CompilationPlan(
        plan_id=str(raw["plan_id"]),
        candidate_id=str(raw["candidate_id"]),
        selected_kind=CompilationKind(raw["selected_kind"]),
        rejected_cheaper_kinds=dict(raw["rejected_cheaper_kinds"]),
        evidence_refs=tuple(raw["evidence_refs"]),
        projected_model_calls=int(raw["projected_model_calls"]),
        expected_disposition=CompilationDisposition(raw["expected_disposition"]),
    )


def _capability_payload(value: CompiledCapability) -> dict[str, Any]:
    return {
        "capability_id": value.capability_id,
        "capability_key": value.capability_key,
        "candidate_id": value.candidate_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "mechanism_id": value.mechanism_id,
        "generalization_profile_id": value.generalization_profile_id,
        "prior_generalized_evidence_ref": value.prior_generalized_evidence_ref,
        "selected_kind": value.selected_kind.value,
        "version": value.version,
        "previous_capability_id": value.previous_capability_id,
        "disposition": value.disposition.value,
        "trigger_contract": value.trigger_contract,
        "compiled_payload": value.compiled_payload,
        "verifier_contract": value.verifier_contract,
        "negative_transfer_boundary": value.negative_transfer_boundary,
        "tested_region": value.tested_region,
        "evidence_refs": value.evidence_refs,
        "source_hashes": value.source_hashes,
        "rollback_action": value.rollback_action,
        "partition": value.partition.value,
        "handoff": value.handoff,
        "deployment_allowed": value.deployment_allowed,
        "fresh_validation_required": value.fresh_validation_required,
    }


def _capability_from(payload: Mapping[str, Any]) -> CompiledCapability:
    raw = dict(payload)
    return CompiledCapability(
        capability_id=str(raw["capability_id"]),
        capability_key=str(raw["capability_key"]),
        candidate_id=str(raw["candidate_id"]),
        failure_snapshot_id=str(raw["failure_snapshot_id"]),
        mechanism_id=str(raw["mechanism_id"]),
        generalization_profile_id=raw.get("generalization_profile_id"),
        prior_generalized_evidence_ref=raw.get("prior_generalized_evidence_ref"),
        selected_kind=CompilationKind(raw["selected_kind"]),
        version=int(raw["version"]),
        previous_capability_id=raw.get("previous_capability_id"),
        disposition=CompilationDisposition(raw["disposition"]),
        trigger_contract=dict(raw["trigger_contract"]),
        compiled_payload=dict(raw["compiled_payload"]),
        verifier_contract=dict(raw["verifier_contract"]),
        negative_transfer_boundary=tuple(raw["negative_transfer_boundary"]),
        tested_region=str(raw["tested_region"]),
        evidence_refs=tuple(raw["evidence_refs"]),
        source_hashes=dict(raw["source_hashes"]),
        rollback_action=str(raw["rollback_action"]),
        partition=Partition(raw["partition"]),
        handoff=str(raw["handoff"]),
        deployment_allowed=bool(raw.get("deployment_allowed", False)),
        fresh_validation_required=bool(raw.get("fresh_validation_required", True)),
    )


@dataclass(frozen=True)
class CompilationStoreValidation:
    ok: bool
    candidate_count: int
    decision_count: int
    capability_count: int
    hash_mismatches: tuple[str, ...]
    broken_lineage: tuple[str, ...]
    duplicate_ids: tuple[str, ...]


_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


class CompilationEvidenceStore:
    """Persist Stage-8 metadata while canonical replay/generalization evidence stays authoritative."""

    def __init__(
        self,
        root: Path,
        *,
        replay_store: ReplayStore,
        mutation_store: Any,
        causal_store: Any,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not callable(getattr(mutation_store, "validate", None)) or not callable(
            getattr(mutation_store, "profiles", None)
        ):
            raise TypeError("mutation_store must expose validate() and profiles()")
        if not callable(getattr(causal_store, "validate", None)):
            raise TypeError("causal_store must expose validate()")
        self.root = Path(root)
        self.replay_store = replay_store
        self.mutation_store = mutation_store
        self.causal_store = causal_store
        self.candidate_path = self.root / "compilation-candidates.jsonl"
        self.decision_path = self.root / "compilation-decisions.jsonl"
        self.capability_path = self.root / "compiled-capabilities.jsonl"
        self.manifest_path = self.root / "SHA256SUMS.csv"
        self.lock_path = self.root / ".compilation-evidence.lock"
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

    def _expected_manifest(self) -> bytes:
        rows: list[str] = []
        for name in _DATA_FILES:
            path = self.root / name
            if path.exists():
                rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()},{name}")
        return (("\n".join(rows) + "\n") if rows else "").encode("ascii")

    def _manifest_ok(self) -> bool:
        expected = self._expected_manifest()
        if not expected:
            return not self.manifest_path.exists() or self.manifest_path.read_bytes() == b""
        return self.manifest_path.exists() and self.manifest_path.read_bytes() == expected

    def _write_manifest(self) -> None:
        expected = self._expected_manifest()
        temporary = self.manifest_path.with_name(self.manifest_path.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(expected)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.manifest_path)
        self._fsync_directory(self.root)

    @staticmethod
    def _rows(
        path: Path,
        decoder: Callable[[Mapping[str, Any]], T],
        id_name: str,
    ) -> list[tuple[str, bytes, T]]:
        if not path.exists():
            return []
        encoded = path.read_bytes()
        if encoded and not encoded.endswith(b"\n"):
            raise ValueError(f"{path.name} must end with newline")
        result: list[tuple[str, bytes, T]] = []
        for number, line in enumerate(encoded.splitlines(), 1):
            if not line:
                raise ValueError(f"{path.name}:{number} is blank")
            payload = json.loads(line.decode("utf-8"))
            if line != _canonical(payload):
                raise ValueError(f"{path.name}:{number} is not canonical JSON")
            value = decoder(payload)
            result.append((str(getattr(value, id_name)), line, value))
        return result

    def _append(
        self,
        *,
        path: Path,
        logical_id: str,
        payload: Mapping[str, Any],
        decoder: Callable[[Mapping[str, Any]], T],
        id_name: str,
    ) -> str:
        line = _canonical(payload)
        with self._transaction_lock():
            if not self._manifest_ok():
                raise ValueError("SHA256 manifest mismatch; refusing append")
            rows = self._rows(path, decoder, id_name)
            matches = [existing for row_id, existing, _ in rows if row_id == logical_id]
            if matches:
                if any(existing != line for existing in matches):
                    raise ValueError("existing logical ID has different canonical content")
                return logical_id
            with path.open("ab") as handle:
                handle.write(line + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._write_manifest()
        return logical_id

    def _require_source_stores(self) -> None:
        replay_validation = self.replay_store.validate()
        mutation_validation = self.mutation_store.validate()
        causal_validation = self.causal_store.validate()
        if not getattr(replay_validation, "ok", False):
            raise ValueError("canonical replay store integrity validation failed")
        if not getattr(mutation_validation, "ok", False):
            raise ValueError("canonical mutation store integrity validation failed")
        if not getattr(causal_validation, "ok", False):
            raise ValueError("canonical causal store integrity validation failed")

    def _require_candidate_lineage(self, candidate: CompilationCandidate) -> None:
        self._require_source_stores()
        if candidate.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH/SEALED protected partition cannot enter Stage-8 compilation")
        try:
            failure = self.replay_store.get_failure(candidate.failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("candidate references unknown failure lineage") from exc
        if failure.partition != candidate.partition:
            raise ValueError("candidate partition differs from canonical failure lineage")

        if candidate.generalization_profile_id is not None:
            matches = [
                profile
                for profile in self.mutation_store.profiles()
                if getattr(profile, "profile_id", None) == candidate.generalization_profile_id
            ]
            if len(matches) != 1:
                raise ValueError("candidate generalization profile is missing or ambiguous")
            profile = matches[0]
            if getattr(profile, "failure_snapshot_id", None) != candidate.failure_snapshot_id:
                raise ValueError("generalization profile failure lineage mismatch")
            if getattr(profile, "mechanism_id", None) != candidate.mechanism_id:
                raise ValueError("generalization profile mechanism lineage mismatch")
            if getattr(profile, "classification", None) != candidate.generalization_class:
                raise ValueError("generalization profile classification mismatch")
            if tuple(getattr(profile, "protected_failures", ())) != ():
                raise ValueError("generalization profile has protected negative-transfer failures")

        bad = _contains_raw_key(_candidate_payload(candidate))
        if bad is not None:
            raise ValueError(f"Stage-8 metadata may not duplicate raw model payload field {bad}")

    def append_candidate(self, candidate: CompilationCandidate) -> str:
        if not isinstance(candidate, CompilationCandidate):
            raise TypeError("candidate must be CompilationCandidate")
        self._require_candidate_lineage(candidate)
        return self._append(
            path=self.candidate_path,
            logical_id=candidate.candidate_id,
            payload=_candidate_payload(candidate),
            decoder=_candidate_from,
            id_name="candidate_id",
        )

    def append_decision(self, plan: CompilationPlan) -> str:
        if not isinstance(plan, CompilationPlan):
            raise TypeError("plan must be CompilationPlan")
        self._require_source_stores()
        try:
            candidate = self.get_candidate(plan.candidate_id)
        except KeyError as exc:
            raise ValueError("compilation decision references unknown candidate") from exc
        if plan.selected_kind not in candidate.supported_kinds:
            raise ValueError("compilation decision selects an unsupported owner")
        if tuple(plan.evidence_refs) != tuple(candidate.evidence_refs):
            raise ValueError("compilation decision evidence differs from candidate evidence")
        return self._append(
            path=self.decision_path,
            logical_id=plan.plan_id,
            payload=_plan_payload(plan),
            decoder=_plan_from,
            id_name="plan_id",
        )

    def append_capability(self, capability: CompiledCapability) -> str:
        if not isinstance(capability, CompiledCapability):
            raise TypeError("capability must be CompiledCapability")
        self._require_source_stores()
        bad = _contains_raw_key(_capability_payload(capability))
        if bad is not None:
            raise ValueError(f"Stage-8 metadata may not duplicate raw model payload field {bad}")
        try:
            candidate = self.get_candidate(capability.candidate_id)
        except KeyError as exc:
            raise ValueError("compiled capability references unknown candidate") from exc
        if capability.failure_snapshot_id != candidate.failure_snapshot_id or capability.mechanism_id != candidate.mechanism_id:
            raise ValueError("compiled capability candidate lineage mismatch")
        if capability.selected_kind not in candidate.supported_kinds:
            raise ValueError("compiled capability owner is not supported by candidate")
        decisions = [
            item for item in self.decisions()
            if item.candidate_id == candidate.candidate_id and item.selected_kind == capability.selected_kind
        ]
        if not decisions:
            raise ValueError("compiled capability requires a committed compilation decision")

        existing = self.capabilities()
        if capability.version == 1:
            if any(item.capability_key == capability.capability_key for item in existing):
                raise ValueError("version 1 already exists for capability key")
        else:
            previous = [item for item in existing if item.capability_id == capability.previous_capability_id]
            if len(previous) != 1:
                raise ValueError("previous capability version is missing")
            parent = previous[0]
            if parent.capability_key != capability.capability_key:
                raise ValueError("previous capability belongs to a different capability key")
            if parent.version != capability.version - 1:
                raise ValueError("compiled capability version chain is not contiguous")
        return self._append(
            path=self.capability_path,
            logical_id=capability.capability_id,
            payload=_capability_payload(capability),
            decoder=_capability_from,
            id_name="capability_id",
        )

    def candidates(self) -> tuple[CompilationCandidate, ...]:
        return tuple(value for _, _, value in self._rows(self.candidate_path, _candidate_from, "candidate_id"))

    def decisions(self) -> tuple[CompilationPlan, ...]:
        return tuple(value for _, _, value in self._rows(self.decision_path, _plan_from, "plan_id"))

    def capabilities(self) -> tuple[CompiledCapability, ...]:
        return tuple(value for _, _, value in self._rows(self.capability_path, _capability_from, "capability_id"))

    def get_candidate(self, candidate_id: str) -> CompilationCandidate:
        matches = [item for item in self.candidates() if item.candidate_id == candidate_id]
        if len(matches) != 1:
            raise KeyError(candidate_id)
        return matches[0]

    def get_capability(self, capability_id: str) -> CompiledCapability:
        matches = [item for item in self.capabilities() if item.capability_id == capability_id]
        if len(matches) != 1:
            raise KeyError(capability_id)
        return matches[0]

    def validate(self) -> CompilationStoreValidation:
        hash_mismatches: list[str] = []
        broken_lineage: list[str] = []
        duplicate_ids: list[str] = []
        candidates: tuple[CompilationCandidate, ...] = ()
        decisions: tuple[CompilationPlan, ...] = ()
        capabilities: tuple[CompiledCapability, ...] = ()

        if not self._manifest_ok():
            hash_mismatches.append(self.manifest_path.name)
        try:
            candidate_rows = self._rows(self.candidate_path, _candidate_from, "candidate_id")
            decision_rows = self._rows(self.decision_path, _plan_from, "plan_id")
            capability_rows = self._rows(self.capability_path, _capability_from, "capability_id")
            candidates = tuple(item for _, _, item in candidate_rows)
            decisions = tuple(item for _, _, item in decision_rows)
            capabilities = tuple(item for _, _, item in capability_rows)
            for rows in (candidate_rows, decision_rows, capability_rows):
                seen: dict[str, bytes] = {}
                for logical_id, encoded, _ in rows:
                    prior = seen.get(logical_id)
                    if prior is not None and prior != encoded:
                        duplicate_ids.append(logical_id)
                    elif prior is not None:
                        duplicate_ids.append(logical_id)
                    else:
                        seen[logical_id] = encoded
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            broken_lineage.append(str(exc))

        if not broken_lineage:
            try:
                self._require_source_stores()
                for candidate in candidates:
                    self._require_candidate_lineage(candidate)
                candidate_map = {item.candidate_id: item for item in candidates}
                for plan in decisions:
                    candidate = candidate_map.get(plan.candidate_id)
                    if candidate is None:
                        raise ValueError("decision references missing candidate")
                    if plan.selected_kind not in candidate.supported_kinds:
                        raise ValueError("decision selects unsupported owner")
                capability_map = {item.capability_id: item for item in capabilities}
                for capability in capabilities:
                    candidate = candidate_map.get(capability.candidate_id)
                    if candidate is None:
                        raise ValueError("capability references missing candidate")
                    if capability.version > 1:
                        parent = capability_map.get(capability.previous_capability_id or "")
                        if parent is None:
                            raise ValueError("capability previous version is missing")
                        if parent.capability_key != capability.capability_key or parent.version != capability.version - 1:
                            raise ValueError("capability version lineage mismatch")
            except (ValueError, TypeError, KeyError) as exc:
                broken_lineage.append(str(exc))

        return CompilationStoreValidation(
            ok=not hash_mismatches and not broken_lineage and not duplicate_ids,
            candidate_count=len(candidates),
            decision_count=len(decisions),
            capability_count=len(capabilities),
            hash_mismatches=tuple(hash_mismatches),
            broken_lineage=tuple(broken_lineage),
            duplicate_ids=tuple(dict.fromkeys(duplicate_ids)),
        )

    def export_catalog(self, path: Path) -> dict[str, Any]:
        validation = self.validate()
        if not validation.ok:
            raise ValueError("compilation store integrity validation failed; refusing catalog export")
        ordered = sorted(
            self.capabilities(),
            key=lambda item: (item.capability_key, item.version, item.capability_id),
        )
        body: dict[str, Any] = {
            "MODEL_CALLS": 0,
            "capabilities": [_json_value(_capability_payload(item)) for item in ordered],
        }
        catalog_hash = hashlib.sha256(_canonical(body)).hexdigest()
        result = {**body, "catalog_hash": catalog_hash}
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        self._fsync_directory(destination.parent)
        return result
