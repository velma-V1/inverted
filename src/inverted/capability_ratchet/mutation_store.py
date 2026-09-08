"""Append-only Stage-6 mutation-study metadata bound to canonical replay evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping, Sequence, TypeVar

from .core import (
    FailureFixture,
    MutationFixture,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayResult,
)
from .mutation_core import (
    GeneralizationClass,
    GeneralizationProfile,
    MutationAxis,
    MutationDirection,
    MutationPolicy,
    MutationSpec,
)
from .replay_store import ReplayStore


T = TypeVar("T")
_RAW_METADATA_KEYS = frozenset(
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


def _required(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mutation metadata mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("mutation metadata numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported mutation metadata value: {type(value).__name__}")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("mutation metadata numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported mutation metadata value: {type(value).__name__}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _contains_raw_metadata(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _RAW_METADATA_KEYS:
                return key
            found = _contains_raw_metadata(item)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _contains_raw_metadata(item)
            if found is not None:
                return found
    return None


def _policy_payload(policy: MutationPolicy) -> dict[str, Any]:
    return policy.to_payload()


def _spec_payload(spec: MutationSpec) -> dict[str, Any]:
    return {
        "axis": spec.axis.value,
        "direction": spec.direction.value,
        "value": spec.value,
        "structural_region_id": spec.structural_region_id,
        "decision_id": spec.decision_id,
        "protected": spec.protected,
        "spec_id": spec.spec_id,
    }


def _spec_from(payload: Mapping[str, Any]) -> MutationSpec:
    return MutationSpec(
        axis=MutationAxis(payload["axis"]),
        direction=MutationDirection(payload["direction"]),
        value=payload["value"],
        structural_region_id=str(payload["structural_region_id"]),
        decision_id=str(payload["decision_id"]),
        protected=bool(payload.get("protected", False)),
        spec_id=str(payload["spec_id"]),
    )


@dataclass(frozen=True)
class MutationStudy:
    study_id: str
    failure_snapshot_id: str
    mechanism_id: str
    source_failure_snapshot_id: str
    source_state_hash: str
    operating_surface_profile_id: str | None
    policy: MutationPolicy
    decision_id: str
    candidate_specs: tuple[MutationSpec, ...]
    protected_spec_ids: tuple[str, ...]
    decision_critical_reason: str | None = None
    synthetic: bool = True

    def __post_init__(self) -> None:
        for name in (
            "study_id",
            "failure_snapshot_id",
            "mechanism_id",
            "source_failure_snapshot_id",
            "decision_id",
        ):
            _required(name, getattr(self, name))
        _sha256("source_state_hash", self.source_state_hash)
        if self.operating_surface_profile_id is not None:
            _required("operating_surface_profile_id", self.operating_surface_profile_id)
        if self.decision_critical_reason is not None:
            _required("decision_critical_reason", self.decision_critical_reason)
        if type(self.synthetic) is not bool:
            raise TypeError("synthetic must be boolean")
        if not isinstance(self.policy, MutationPolicy):
            if not isinstance(self.policy, Mapping):
                raise TypeError("policy must be MutationPolicy")
            object.__setattr__(self, "policy", MutationPolicy(**dict(self.policy)))
        if isinstance(self.candidate_specs, (str, bytes, bytearray)) or not isinstance(
            self.candidate_specs, (list, tuple)
        ):
            raise TypeError("candidate_specs must be a sequence")
        specs = tuple(self.candidate_specs)
        if not specs or any(not isinstance(item, MutationSpec) for item in specs):
            raise ValueError("candidate_specs must contain MutationSpec values")
        ids = tuple(item.spec_id for item in specs)
        if len(set(ids)) != len(ids):
            raise ValueError("candidate_specs must have unique logical IDs")
        protected = tuple(self.protected_spec_ids)
        if any(not isinstance(item, str) or not item.strip() for item in protected):
            raise TypeError("protected_spec_ids must contain nonblank strings")
        if len(set(protected)) != len(protected):
            raise ValueError("protected_spec_ids must be unique")
        if not set(protected).issubset(set(ids)):
            raise ValueError("protected_spec_ids must reference candidate_specs")
        if any(spec.protected != (spec.spec_id in set(protected)) for spec in specs):
            raise ValueError("protected_spec_ids must exactly match protected candidate specs")
        object.__setattr__(self, "candidate_specs", specs)
        object.__setattr__(self, "protected_spec_ids", protected)


@dataclass(frozen=True)
class MutationOutcome:
    outcome_id: str
    study_id: str
    mutation_fixture_id: str
    replay_result_id: str
    axis: MutationAxis
    direction: MutationDirection
    structural_region_id: str
    protected: bool
    semantic_pass: bool
    contract_pass: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "outcome_id",
            "study_id",
            "mutation_fixture_id",
            "replay_result_id",
            "structural_region_id",
        ):
            _required(name, getattr(self, name))
        if not isinstance(self.axis, MutationAxis):
            object.__setattr__(self, "axis", MutationAxis(self.axis))
        if not isinstance(self.direction, MutationDirection):
            object.__setattr__(self, "direction", MutationDirection(self.direction))
        for name in ("protected", "semantic_pass", "contract_pass"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        bad = _contains_raw_metadata(self.metadata)
        if bad is not None:
            raise ValueError(f"Stage-6 metadata may not duplicate raw model payload field {bad}")
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True)
class MutationStoreValidation:
    ok: bool
    study_count: int
    outcome_count: int
    profile_count: int
    hash_mismatches: tuple[str, ...]
    broken_lineage: tuple[str, ...]
    duplicate_ids: tuple[str, ...]


def _study_payload(study: MutationStudy) -> dict[str, Any]:
    return {
        "study_id": study.study_id,
        "failure_snapshot_id": study.failure_snapshot_id,
        "mechanism_id": study.mechanism_id,
        "source_failure_snapshot_id": study.source_failure_snapshot_id,
        "source_state_hash": study.source_state_hash,
        "operating_surface_profile_id": study.operating_surface_profile_id,
        "policy": _policy_payload(study.policy),
        "decision_id": study.decision_id,
        "candidate_specs": tuple(_spec_payload(item) for item in study.candidate_specs),
        "protected_spec_ids": study.protected_spec_ids,
        "decision_critical_reason": study.decision_critical_reason,
        "synthetic": study.synthetic,
    }


def _study_from(payload: Mapping[str, Any]) -> MutationStudy:
    raw = dict(payload)
    return MutationStudy(
        study_id=raw["study_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        mechanism_id=raw["mechanism_id"],
        source_failure_snapshot_id=raw["source_failure_snapshot_id"],
        source_state_hash=raw["source_state_hash"],
        operating_surface_profile_id=raw.get("operating_surface_profile_id"),
        policy=MutationPolicy(**dict(raw["policy"])),
        decision_id=raw["decision_id"],
        candidate_specs=tuple(_spec_from(item) for item in raw["candidate_specs"]),
        protected_spec_ids=tuple(raw.get("protected_spec_ids", ())),
        decision_critical_reason=raw.get("decision_critical_reason"),
        synthetic=bool(raw.get("synthetic", True)),
    )


def _outcome_payload(outcome: MutationOutcome) -> dict[str, Any]:
    return {
        "outcome_id": outcome.outcome_id,
        "study_id": outcome.study_id,
        "mutation_fixture_id": outcome.mutation_fixture_id,
        "replay_result_id": outcome.replay_result_id,
        "axis": outcome.axis.value,
        "direction": outcome.direction.value,
        "structural_region_id": outcome.structural_region_id,
        "protected": outcome.protected,
        "semantic_pass": outcome.semantic_pass,
        "contract_pass": outcome.contract_pass,
        "metadata": outcome.metadata,
    }


def _outcome_from(payload: Mapping[str, Any]) -> MutationOutcome:
    raw = dict(payload)
    return MutationOutcome(
        outcome_id=raw["outcome_id"],
        study_id=raw["study_id"],
        mutation_fixture_id=raw["mutation_fixture_id"],
        replay_result_id=raw["replay_result_id"],
        axis=MutationAxis(raw["axis"]),
        direction=MutationDirection(raw["direction"]),
        structural_region_id=raw["structural_region_id"],
        protected=bool(raw["protected"]),
        semantic_pass=bool(raw["semantic_pass"]),
        contract_pass=bool(raw["contract_pass"]),
        metadata=dict(raw.get("metadata", {})),
    )


def _profile_payload(profile: GeneralizationProfile) -> dict[str, Any]:
    bad = _contains_raw_metadata(profile.metadata)
    if bad is not None:
        raise ValueError(f"Stage-6 metadata may not duplicate raw model payload field {bad}")
    return {
        "profile_id": profile.profile_id,
        "study_id": profile.study_id,
        "failure_snapshot_id": profile.failure_snapshot_id,
        "mechanism_id": profile.mechanism_id,
        "policy": _policy_payload(profile.policy),
        "mutation_result_ids": profile.mutation_result_ids,
        "successful_mutation_fixture_ids": profile.successful_mutation_fixture_ids,
        "failed_mutation_fixture_ids": profile.failed_mutation_fixture_ids,
        "axis_successes": profile.axis_successes,
        "region_successes": profile.region_successes,
        "harder_successes": profile.harder_successes,
        "success_rate": profile.success_rate,
        "protected_failures": profile.protected_failures,
        "classification": profile.classification.value,
        "unresolved_boundaries": profile.unresolved_boundaries,
        "metadata": profile.metadata,
    }


def _profile_from(payload: Mapping[str, Any]) -> GeneralizationProfile:
    raw = dict(payload)
    return GeneralizationProfile(
        profile_id=raw["profile_id"],
        study_id=raw["study_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        mechanism_id=raw["mechanism_id"],
        policy=MutationPolicy(**dict(raw["policy"])),
        mutation_result_ids=tuple(raw["mutation_result_ids"]),
        successful_mutation_fixture_ids=tuple(raw["successful_mutation_fixture_ids"]),
        failed_mutation_fixture_ids=tuple(raw["failed_mutation_fixture_ids"]),
        axis_successes=dict(raw["axis_successes"]),
        region_successes=dict(raw["region_successes"]),
        harder_successes=int(raw["harder_successes"]),
        success_rate=float(raw["success_rate"]),
        protected_failures=tuple(raw["protected_failures"]),
        classification=GeneralizationClass(raw["classification"]),
        unresolved_boundaries=tuple(raw["unresolved_boundaries"]),
        metadata=dict(raw.get("metadata", {})),
    )


_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


class MutationEvidenceStore:
    """Persist only Stage-6 scientific metadata; replay bytes remain in ReplayStore."""

    def __init__(self, root: Path, *, replay_store: ReplayStore, surface_store: Any) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not callable(getattr(surface_store, "profiles", None)):
            raise TypeError("surface_store must expose profiles()")
        self.root = Path(root)
        self.replay_store = replay_store
        self.surface_store = surface_store
        self.study_path = self.root / "mutation-studies.jsonl"
        self.study_manifest_path = self.root / "mutation-studies.sha256"
        self.outcome_path = self.root / "mutation-outcomes.jsonl"
        self.outcome_manifest_path = self.root / "mutation-outcomes.sha256"
        self.profile_path = self.root / "generalization-profiles.jsonl"
        self.profile_manifest_path = self.root / "generalization-profiles.sha256"
        self.lock_path = self.root / ".mutation-evidence.lock"
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

    @staticmethod
    def _manifest_bytes(path: Path) -> bytes:
        encoded = path.read_bytes() if path.exists() else b""
        return hashlib.sha256(encoded).hexdigest().encode("ascii") + b"\n"

    def _write_manifest(self, path: Path, manifest: Path) -> None:
        temporary = manifest.with_name(manifest.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(self._manifest_bytes(path))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, manifest)
        self._fsync_directory(manifest.parent)

    @staticmethod
    def _rows(path: Path, decoder: Callable[[Mapping[str, Any]], T], id_name: str) -> list[tuple[str, bytes, T]]:
        if not path.exists():
            return []
        encoded = path.read_bytes()
        if encoded and not encoded.endswith(b"\n"):
            raise ValueError(f"{path.name} must end with newline")
        rows: list[tuple[str, bytes, T]] = []
        for number, line in enumerate(encoded.splitlines(), 1):
            if not line:
                raise ValueError(f"{path.name}:{number} is blank")
            payload = json.loads(line.decode("utf-8"))
            if line != _canonical(payload):
                raise ValueError(f"{path.name}:{number} is not canonical JSON")
            value = decoder(payload)
            logical_id = getattr(value, id_name)
            rows.append((logical_id, line, value))
        return rows

    def _append(
        self,
        *,
        path: Path,
        manifest: Path,
        logical_id: str,
        payload: Mapping[str, Any],
        decoder: Callable[[Mapping[str, Any]], T],
        id_name: str,
    ) -> str:
        line = _canonical(payload)
        with self._transaction_lock():
            if path.exists():
                if not manifest.exists() or manifest.read_bytes() != self._manifest_bytes(path):
                    raise ValueError(f"{manifest.name} mismatch; refusing append")
            elif manifest.exists():
                raise ValueError(f"{manifest.name} exists without source; refusing append")
            rows = self._rows(path, decoder, id_name)
            matches = [existing for row_id, existing, _ in rows if row_id == logical_id]
            if matches:
                if any(existing != line for existing in matches):
                    raise ValueError("existing logical ID has different canonical content")
                return logical_id
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab") as handle:
                handle.write(line + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._write_manifest(path, manifest)
        return logical_id

    def _root(self, failure: FailureFixture) -> FailureFixture:
        current = failure
        seen: set[str] = set()
        while current.parent_failure_snapshot_id is not None:
            if current.failure_snapshot_id in seen:
                raise ValueError("failure lineage cycle")
            seen.add(current.failure_snapshot_id)
            current = self.replay_store.get_failure(current.parent_failure_snapshot_id)
        return current

    def _movement_exists(self, failure_snapshot_id: str, mechanism_id: str) -> bool:
        return any(
            isinstance(record, PromotionEvent)
            and record.failure_snapshot_id == failure_snapshot_id
            and record.mechanism_id == mechanism_id
            and record.to_state is PromotionState.MOVEMENT
            for record in self.replay_store.records()
        )

    def _matching_surface_profile(self, study: MutationStudy) -> bool:
        if study.operating_surface_profile_id is None:
            return False
        return any(
            getattr(profile, "profile_id", None) == study.operating_surface_profile_id
            and getattr(profile, "failure_snapshot_id", None) == study.failure_snapshot_id
            and getattr(profile, "mechanism_id", None) == study.mechanism_id
            for profile in self.surface_store.profiles()
        )

    def _require_study_lineage(self, study: MutationStudy) -> None:
        try:
            source = self.replay_store.get_failure(study.source_failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("mutation study references unknown source failure") from exc
        if source.state_hash != study.source_state_hash:
            raise ValueError("mutation study source state mismatch")
        if self._root(source).failure_snapshot_id != study.failure_snapshot_id:
            raise ValueError("mutation study root failure mismatch")
        if study.synthetic and source.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("synthetic mutation study cannot consume FRESH or SEALED lineage")
        has_profile = self._matching_surface_profile(study)
        has_movement = self._movement_exists(study.failure_snapshot_id, study.mechanism_id)
        if study.operating_surface_profile_id is not None and not has_profile:
            raise ValueError("mutation study references unknown or mismatched surface profile")
        if not (has_profile or has_movement or study.decision_critical_reason):
            raise ValueError(
                "mutation study requires MOVEMENT, a matching surface profile, or decision-critical reason"
            )

    def append_study(self, study: MutationStudy) -> str:
        if not isinstance(study, MutationStudy):
            raise TypeError("study must be MutationStudy")
        self._require_study_lineage(study)
        return self._append(
            path=self.study_path,
            manifest=self.study_manifest_path,
            logical_id=study.study_id,
            payload=_study_payload(study),
            decoder=_study_from,
            id_name="study_id",
        )

    def studies(self, mechanism_id: str | None = None) -> tuple[MutationStudy, ...]:
        with self._transaction_lock():
            values = tuple(row[2] for row in self._rows(self.study_path, _study_from, "study_id"))
        if mechanism_id is None:
            return values
        return tuple(item for item in values if item.mechanism_id == mechanism_id)

    def _mutation_fixture(self, fixture_id: str) -> MutationFixture:
        matches = [
            record for record in self.replay_store.records()
            if isinstance(record, MutationFixture) and record.mutation_fixture_id == fixture_id
        ]
        if len(matches) != 1:
            raise ValueError(f"mutation fixture {fixture_id} is not uniquely stored")
        return matches[0]

    def _replay_result(self, result_id: str) -> ReplayResult:
        matches = [
            record for record in self.replay_store.records()
            if isinstance(record, ReplayResult) and record.replay_result_id == result_id
        ]
        if len(matches) != 1:
            raise ValueError(f"replay result {result_id} is not uniquely stored")
        return matches[0]

    def _require_outcome_lineage(self, outcome: MutationOutcome) -> None:
        studies = {item.study_id: item for item in self.studies()}
        study = studies.get(outcome.study_id)
        if study is None:
            raise ValueError("mutation outcome references unknown study")
        fixture = self._mutation_fixture(outcome.mutation_fixture_id)
        if (
            fixture.failure_snapshot_id != study.failure_snapshot_id
            or fixture.mechanism_id != study.mechanism_id
            or fixture.source_failure_snapshot_id != study.source_failure_snapshot_id
            or fixture.source_state_hash != study.source_state_hash
        ):
            raise ValueError("mutation fixture lineage does not match study")
        spec_ids = {item.spec_id for item in study.candidate_specs}
        if fixture.metadata.get("mutation_spec_id") not in spec_ids:
            raise ValueError("mutation fixture is not a candidate in the study")
        if (
            outcome.axis is not fixture.mutation_axis
            or outcome.direction is not fixture.mutation_direction
            or outcome.structural_region_id != fixture.structural_region_id
            or outcome.protected != bool(fixture.metadata.get("protected", False))
        ):
            raise ValueError("mutation outcome geometry does not match mutation fixture")
        result = self._replay_result(outcome.replay_result_id)
        if result.metadata.get("mutation_fixture_id") != fixture.mutation_fixture_id:
            raise ValueError("replay result is not the matching mutation fixture result")
        if (
            result.failure_snapshot_id != study.failure_snapshot_id
            or result.parent_failure_snapshot_id != fixture.source_failure_snapshot_id
            or result.parent_state_hash != fixture.source_state_hash
            or result.partition != fixture.partition
        ):
            raise ValueError("matching mutation replay result has wrong lineage")
        if outcome.semantic_pass != result.semantic_pass or outcome.contract_pass != result.contract_pass:
            raise ValueError("mutation outcome pass flags differ from replay result")

    def append_outcome(self, outcome: MutationOutcome) -> str:
        if not isinstance(outcome, MutationOutcome):
            raise TypeError("outcome must be MutationOutcome")
        self._require_outcome_lineage(outcome)
        return self._append(
            path=self.outcome_path,
            manifest=self.outcome_manifest_path,
            logical_id=outcome.outcome_id,
            payload=_outcome_payload(outcome),
            decoder=_outcome_from,
            id_name="outcome_id",
        )

    def outcomes(self, study_id: str | None = None) -> tuple[MutationOutcome, ...]:
        with self._transaction_lock():
            values = tuple(row[2] for row in self._rows(self.outcome_path, _outcome_from, "outcome_id"))
        if study_id is None:
            return values
        return tuple(item for item in values if item.study_id == study_id)

    def _require_profile_lineage(self, profile: GeneralizationProfile) -> None:
        studies = {item.study_id: item for item in self.studies()}
        study = studies.get(profile.study_id)
        if study is None:
            raise ValueError("generalization profile references unknown study")
        if profile.failure_snapshot_id != study.failure_snapshot_id or profile.mechanism_id != study.mechanism_id:
            raise ValueError("generalization profile lineage differs from study")
        if profile.policy != study.policy:
            raise ValueError("generalization profile policy differs from study")
        outcomes = tuple(self.outcomes(study.study_id))
        by_result = {item.replay_result_id: item for item in outcomes}
        by_fixture = {item.mutation_fixture_id: item for item in outcomes}
        missing_results = [item for item in profile.mutation_result_ids if item not in by_result]
        if missing_results:
            raise ValueError(f"generalization profile result does not resolve to stored outcome: {missing_results}")
        for fixture_id in profile.successful_mutation_fixture_ids:
            outcome = by_fixture.get(fixture_id)
            if outcome is None or not (outcome.semantic_pass and outcome.contract_pass):
                raise ValueError(f"generalization profile successful fixture has no passing outcome: {fixture_id}")
        for fixture_id in profile.failed_mutation_fixture_ids:
            outcome = by_fixture.get(fixture_id)
            if outcome is None or (outcome.semantic_pass and outcome.contract_pass):
                raise ValueError(f"generalization profile failed fixture has no failing outcome: {fixture_id}")
        for fixture_id in profile.protected_failures:
            outcome = by_fixture.get(fixture_id)
            if outcome is None or not outcome.protected or (outcome.semantic_pass and outcome.contract_pass):
                raise ValueError(f"protected failure does not resolve to a protected failing outcome: {fixture_id}")

    def append_profile(self, profile: GeneralizationProfile) -> str:
        if not isinstance(profile, GeneralizationProfile):
            raise TypeError("profile must be GeneralizationProfile")
        self._require_profile_lineage(profile)
        return self._append(
            path=self.profile_path,
            manifest=self.profile_manifest_path,
            logical_id=profile.profile_id,
            payload=_profile_payload(profile),
            decoder=_profile_from,
            id_name="profile_id",
        )

    def profiles(self, study_id: str | None = None) -> tuple[GeneralizationProfile, ...]:
        with self._transaction_lock():
            values = tuple(row[2] for row in self._rows(self.profile_path, _profile_from, "profile_id"))
        if study_id is None:
            return values
        return tuple(item for item in values if item.study_id == study_id)

    @staticmethod
    def _manifest_mismatch(path: Path, manifest: Path) -> bool:
        if not path.exists():
            return manifest.exists()
        try:
            expected = hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n"
            return manifest.read_bytes() != expected
        except OSError:
            return True

    def validate(self) -> MutationStoreValidation:
        mismatches: set[str] = set()
        duplicates: set[str] = set()
        broken: list[str] = []
        specs: Sequence[tuple[Path, Path, Callable[[Mapping[str, Any]], Any], str]] = (
            (self.study_path, self.study_manifest_path, _study_from, "study_id"),
            (self.outcome_path, self.outcome_manifest_path, _outcome_from, "outcome_id"),
            (self.profile_path, self.profile_manifest_path, _profile_from, "profile_id"),
        )
        decoded: list[tuple[Any, ...]] = []
        with self._transaction_lock():
            for path, manifest, decoder, id_name in specs:
                if self._manifest_mismatch(path, manifest):
                    mismatches.add(manifest.name)
                try:
                    rows = self._rows(path, decoder, id_name)
                except Exception as exc:
                    mismatches.add(path.name)
                    broken.append(f"{path.name}: {type(exc).__name__}: {exc}")
                    decoded.append(())
                    continue
                seen: set[str] = set()
                values: list[Any] = []
                for logical_id, _, value in rows:
                    if logical_id in seen:
                        duplicates.add(f"{id_name}:{logical_id}")
                    seen.add(logical_id)
                    values.append(value)
                decoded.append(tuple(values))
        studies, outcomes, profiles = decoded  # type: ignore[assignment]

        replay_validation = self.replay_store.validate()
        if not replay_validation.ok:
            broken.append("canonical replay store failed integrity validation")
        validate_surface = getattr(self.surface_store, "validate", None)
        if callable(validate_surface):
            try:
                if not validate_surface().ok:
                    broken.append("operating surface store failed integrity validation")
            except Exception as exc:
                broken.append(f"operating surface validation failed: {exc}")

        for study in studies:
            try:
                self._require_study_lineage(study)
            except Exception as exc:
                broken.append(f"study {study.study_id}: {exc}")
        for outcome in outcomes:
            try:
                self._require_outcome_lineage(outcome)
            except Exception as exc:
                broken.append(f"outcome {outcome.outcome_id}: {exc}")
        for profile in profiles:
            try:
                self._require_profile_lineage(profile)
            except Exception as exc:
                broken.append(f"profile {profile.profile_id}: {exc}")

        return MutationStoreValidation(
            ok=not mismatches and not duplicates and not broken,
            study_count=len(studies),
            outcome_count=len(outcomes),
            profile_count=len(profiles),
            hash_mismatches=tuple(sorted(mismatches)),
            broken_lineage=tuple(broken),
            duplicate_ids=tuple(sorted(duplicates)),
        )
